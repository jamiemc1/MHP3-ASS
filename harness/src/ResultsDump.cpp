#include "stdafx.h"
#include "ResultsDump.h"
#include "Fixtures.h"
#include "Json.h"
#include "Armor.h"
#include "Common.h"
#include "Decoration.h"
#include "LoadedData.h"
#include "QueryFile.h"
#include "Results.h"
#include "Skill.h"
#include "Solution.h"
#include "Workers.h"

using namespace System;
using namespace System::Collections::Generic;
using namespace QueryFile;
using namespace Workers;

namespace
{
	// Form1::AddSolution( String^ line ), Form1.h:342-379. Returns where the
	// line went: 'a' all_solutions (and the charm map), 'n' no_charm_solutions,
	// 'd' dropped as a duplicate.
	wchar_t AddSolutionLine( ResultSet^ results, String^ line )
	{
		List_t< String^ > split;
		Utility::SplitString( %split, line, L' ' );
		Solution^ solution = gcnew Solution;
		for( unsigned i = 0; i < 5; ++i )
			solution->armors.Add( Armor::static_armors[ i ][ Convert::ToUInt32( split[ i ] ) ] );
		const unsigned num_decorations = Convert::ToUInt32( split[ 9 ] );
		for( unsigned i = 0; i < num_decorations; ++i )
			solution->decorations.Add( Decoration::static_decorations[ Convert::ToUInt32( split[ 10 + i ] ) ] );

		const unsigned num_skills = Convert::ToUInt32( split[ 10 + num_decorations ] );
		for( unsigned i = 0; i < num_skills; ++i )
			solution->extra_skills.Add( Skill::static_skills[ Convert::ToUInt32( split[ 11 + num_decorations + i ] ) ] );

		const unsigned charm_start = 11 + num_decorations + num_skills;
		if( charm_start < unsigned( split.Count ) )
		{
			solution->charm = gcnew Charm;
			solution->charm->num_slots = Convert::ToUInt32( split[ charm_start ] );
			const unsigned num_abilities = Convert::ToUInt32( split[ charm_start + 1 ] );
			for( unsigned i = 0; i < num_abilities; ++i )
			{
				Ability^ ability = Ability::static_abilities[ Convert::ToUInt32( split[ charm_start + 3 + i * 2 ] ) ];
				const int amount = Convert::ToInt32( split[ charm_start + 2 + i * 2 ] );
				solution->charm->abilities.Add( gcnew AbilityPair( ability, amount ) );
			}
		}

		solution->CalculateData();
		solution->total_slots_spare = Convert::ToUInt32( split[ 5 ] );
		solution->slots_spare = gcnew cli::array< unsigned >( 4 );
		for( unsigned i = 1; i <= 3; ++i )
			solution->slots_spare[ i ] = Convert::ToUInt32( split[ 5 + i ] );
		if( solution->charm )
			return results->AddSolution( solution->charm->GetName(), solution ) ? L'a' : L'd';
		results->no_charm_solutions.Add( solution );
		return L'n';
	}

	// The solution part of LoadConfig, Form1.h:430-434. Returns each line's
	// placement, in file order.
	String^ LoadSolutions( ResultSet^ results, IO::StreamReader^ fin )
	{
		Text::StringBuilder^ placements = gcnew Text::StringBuilder;
		results->ClearForLoad();
		while( !fin->EndOfStream )
			placements->Append( AddSolutionLine( results, fin->ReadLine() ) );
		return placements->ToString();
	}

	// The solution part of SaveConfig, Form1.h:495-539, encoded as
	// StreamWriter( file ) writes it: UTF-8 without a BOM, CRLF line ends.
	array< Byte >^ SaveSolutions( ResultSet^ results )
	{
		IO::MemoryStream^ stream = gcnew IO::MemoryStream;
		IO::StreamWriter^ fout = gcnew IO::StreamWriter( stream, gcnew Text::UTF8Encoding( false ) );
		try
		{
			for each( Solution^ solution in results->all_solutions )
			{
				fout->Write( SolutionLine( solution ) );
				fout->WriteLine();
			}
			fout->Flush();
			return stream->ToArray();
		}
		finally
		{
			delete fout;
		}
	}

	IO::StreamReader^ Reader( array< Byte >^ bytes )
	{
		return gcnew IO::StreamReader( gcnew IO::MemoryStream( bytes ) );
	}

	// What CalculateData and the slot fields leave on a loaded solution.
	String^ StatsLine( Solution^ solution )
	{
		array< Object^ >^ fields = {
			solution->defence, solution->max_defence, solution->rarity, solution->difficulty,
			solution->fire_res, solution->ice_res, solution->thunder_res, solution->water_res, solution->dragon_res,
			solution->total_slots_spare, solution->slots_spare[ 1 ], solution->slots_spare[ 2 ], solution->slots_spare[ 3 ] };
		return String::Join( L" ", fields );
	}

	String^ StatsSha256( List_t< Solution^ >% solutions )
	{
		Text::StringBuilder^ text = gcnew Text::StringBuilder;
		for each( Solution^ solution in solutions )
			text->Append( StatsLine( solution ) )->Append( L'\n' );
		return Fixtures::Sha256Hex( ( gcnew Text::UTF8Encoding( false ) )->GetBytes( text->ToString() ) );
	}

	void WriteCounts( JsonWriter^ json, ResultSet^ results )
	{
		json->Field( L"all_count", results->all_solutions.Count );
		json->Field( L"no_charm_count", results->no_charm_solutions.Count );
		json->Key( L"charm_map" );
		json->BeginArray();
		for each( KeyValuePair< String^, List_t< Solution^ >^ > entry in results->charm_solution_map )
		{
			json->BeginObject();
			json->Field( L"name", entry.Key );
			json->Field( L"count", entry.Value->Count );
			json->EndObject();
		}
		json->EndArray();
	}

	void WriteLoad( JsonWriter^ json, String^ step, ResultSet^ results, String^ placements )
	{
		json->BeginObject();
		json->Field( L"step", step );
		json->Field( L"line_count", placements->Length );
		json->Field( L"placements", placements );
		WriteCounts( json, results );
		json->Field( L"all_stats_sha256", StatsSha256( results->all_solutions ) );
		json->Field( L"no_charm_stats_sha256", StatsSha256( results->no_charm_solutions ) );
		// LoadConfig ends with SaveConfig (Form1.h:455-456).
		json->Field( L"resaved_sha256", Fixtures::Sha256Hex( SaveSolutions( results ) ) );
		json->EndObject();
	}
}

void ResultsDump::RunSearch( String^ query_path, String^ out_path )
{
	JsonObject^ spec = Read( query_path );
	LoadedData^ data = gcnew LoadedData;
	LoadMyCharms( GetArray( spec, L"my_charms" ) );
	Query^ query = FormulateQuery( data, spec );
	const int charm_select = CharmSelectIndex( GetString( spec, L"charm_mode" ) );

	ResultSet^ searched = gcnew ResultSet;
	List< Charm^ >^ worker_charms = query->skills.Count > 0 ? WorkerCharms( query, charm_select ) : gcnew List< Charm^ >;
	for each( Charm^ charm in worker_charms )
		searched->AddSolutions( RunWorker( query, charm ) );
	array< Byte >^ saved = SaveSolutions( searched );

	JsonWriter^ json = gcnew JsonWriter;
	json->BeginObject();
	json->Field( L"id", GetString( spec, L"id" ) );
	json->Field( L"query_json", Serialize( spec ) );
	json->Key( L"steps" );
	json->BeginArray();

	json->BeginObject();
	json->Field( L"step", L"save" );
	WriteCounts( json, searched );
	json->Field( L"saved_sha256", Fixtures::Sha256Hex( saved ) );
	json->EndObject();

	ResultSet^ fresh = gcnew ResultSet;
	WriteLoad( json, L"load", fresh, LoadSolutions( fresh, Reader( saved ) ) );
	WriteLoad( json, L"load_after_search", searched, LoadSolutions( searched, Reader( saved ) ) );

	json->EndArray();
	json->EndObject();
	json->WriteToFile( out_path );
}

void ResultsDump::RunFile( String^ cfg_path, String^ out_path )
{
	JsonWriter^ json = gcnew JsonWriter;
	json->BeginObject();
	IO::StreamReader fin( cfg_path );
	String^ version = fin.ReadLine();
	json->Field( L"version", version );
	json->Key( L"steps" );
	json->BeginArray();
	// LoadConfig ignores any other version (Form1.h:388-393).
	if( version == L"1" || version == L"2" )
	{
		// Form1::LoadLanguages (Form1.h:331-340) names the menu items LoadConfig indexes.
		array< String^ >^ langs = IO::Directory::GetDirectories( L"Data/Languages" );
		String^ lang = langs[ Convert::ToUInt32( fin.ReadLine() ) ];
		StringTable::LoadLanguage( lang->Substring( lang->LastIndexOf( L'\\' ) + 1 ) );

		// The options and skill rows (Form1.h:399-424): 12 lines, then 4 per row.
		const int num_skills = version == L"2" ? 6 : 5;
		for( int i = 0; i < 12 + 4 * num_skills; ++i )
			fin.ReadLine();

		ResultSet^ results = gcnew ResultSet;
		WriteLoad( json, L"load", results, LoadSolutions( results, %fin ) );
	}
	json->EndArray();
	json->EndObject();
	fin.Close();
	json->WriteToFile( out_path );
}
