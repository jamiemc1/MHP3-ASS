#include "stdafx.h"
#include "SearchDump.h"
#include "Fixtures.h"
#include "Json.h"
#include "Armor.h"
#include "CharmDatabase.h"
#include "Decoration.h"
#include "LoadedData.h"
#include "QueryFile.h"
#include "Skill.h"
#include "Solution.h"
#include "Workers.h"

using namespace System;
using namespace System::Collections::Generic;
using namespace QueryFile;
using namespace Workers;

namespace
{
	// Form1::backgroundWorker1_DoWork, Form1.h:1852-1930, without progress
	// reporting or cancellation. The GUI hands solutions over in batches, but
	// always in this order.
	List< Solution^ >^ RunWorker( Query^ query, Charm^ charm_template )
	{
		List< Solution^ >^ solutions = gcnew List< Solution^ >;
		AddEmptySlotPieces( query );
		List_t< Armor^ >^ head  = query->rel_armor[ int( Armor::ArmorType::HEAD ) ];
		List_t< Armor^ >^ body  = query->rel_armor[ int( Armor::ArmorType::BODY ) ];
		List_t< Armor^ >^ arms  = query->rel_armor[ int( Armor::ArmorType::ARMS ) ];
		List_t< Armor^ >^ waist = query->rel_armor[ int( Armor::ArmorType::WAIST ) ];
		List_t< Armor^ >^ legs  = query->rel_armor[ int( Armor::ArmorType::LEGS ) ];

		for( int i = 0; i < head->Count; ++i )
		{
			for( int j = 0; j < body->Count; ++j )
			{
				for( int k = 0; k < arms->Count; ++k )
				{
					for( int l = 0; l < waist->Count; ++l )
					{
						for( int m = 0; m < legs->Count; ++m )
						{
							array< Armor^ >^ armors = { head[ i ], body[ j ], arms[ k ], waist[ l ], legs[ m ] };
							Solution^ job = NewJob( armors, charm_template );

							if( job->MatchesQuery( query ) )
								solutions->Add( job );
						}
					}
				}
			}
		}
		return solutions;
	}

	// Form1's result collection: HashArmor, SolutionExists, AddSolution and
	// AddSolutions (Form1.h:1691-1746).
	ref class ResultSet
	{
	public:
		List_t< Solution^ > all_solutions;

		// Returns the solutions it kept, in the order it appended them.
		List< Solution^ >^ AddSolutions( List_t< Solution^ >^ solutions )
		{
			List< Solution^ >^ added = gcnew List< Solution^ >;
			for each( Solution^ sol in solutions )
			{
				if( sol->charm )
				{
					if( AddSolution( sol->charm->GetName(), sol ) )
						added->Add( sol );
				}
				else
				{
					all_solutions.Add( sol );
					added->Add( sol );
				}
			}
			return added;
		}

	private:
		Dictionary< String^, Dictionary< __int64, bool >^ > existing_armor;

		__int64 HashArmor( List_t< Armor^ >% armors )
		{
			__int64 res = 0;
			for( int i = 0; i < armors.Count; ++i )
			{
				res += armors[ i ]->index << ( i * 3 );
			}
			return res;
		}

		bool SolutionExists( String^ charm, Solution^ sol )
		{
			if( !existing_armor.ContainsKey( charm ) )
			{
				existing_armor.Add( charm, gcnew Dictionary< __int64, bool > );
				existing_armor[ charm ]->Add( HashArmor( sol->armors ), true );
				return false;
			}
			else
			{
				Dictionary< __int64, bool >^ set = existing_armor[ charm ];
				const __int64 armor_hash = HashArmor( sol->armors );
				if( set->ContainsKey( armor_hash ) )
					return true;
				else
				{
					set->Add( armor_hash, true );
					return false;
				}
			}
		}

		bool AddSolution( String^ charm, Solution^ sol )
		{
			if( SolutionExists( charm, sol ) ) return false;
			all_solutions.Add( sol );
			return true;
		}
	};

	// One solution line of Form1::SaveConfig, Form1.h:495-538 (without the newline).
	String^ SolutionLine( Solution^ solution )
	{
		Text::StringBuilder^ line = gcnew Text::StringBuilder;
		for( unsigned i = 0; i < 5; ++i )
		{
			line->Append( Convert::ToString( Utility::GetIndexOf( Armor::static_armors[ i ], solution->armors[ i ] ) ) );
			line->Append( L" " );
		}
		line->Append( Convert::ToString( solution->total_slots_spare ) );
		line->Append( L" " );
		for( unsigned i = 1; i <= 3; ++i )
		{
			line->Append( Convert::ToString( solution->slots_spare[ i ] ) );
			line->Append( L" " );
		}
		line->Append( Convert::ToString( solution->decorations.Count ) );
		line->Append( L" " );
		for each( Decoration^ decoration in solution->decorations )
		{
			line->Append( Convert::ToString( Utility::GetIndexOf( %Decoration::static_decorations, decoration ) ) );
			line->Append( L" " );
		}
		line->Append( Convert::ToString( solution->extra_skills.Count ) );
		line->Append( L" " );
		for each( Skill^ skill in solution->extra_skills )
		{
			line->Append( Convert::ToString( Utility::GetIndexOf( %Skill::static_skills, skill ) ) );
			line->Append( L" " );
		}
		if( solution->charm )
		{
			line->Append( Convert::ToString( solution->charm->num_slots ) );
			line->Append( L" " );
			line->Append( Convert::ToString( solution->charm->abilities.Count ) );
			line->Append( L" " );
			for each( AbilityPair^ ap in solution->charm->abilities )
			{
				line->Append( Convert::ToString( ap->amount ) );
				line->Append( L" " );
				line->Append( Convert::ToString( Utility::GetIndexOf( %Ability::static_abilities, ap->ability ) ) );
				line->Append( L" " );
			}
		}
		return line->ToString();
	}

	// The text of a lines file, before compression: each line ends in '\n'.
	String^ LinesText( List< String^ >^ lines )
	{
		Text::StringBuilder^ text = gcnew Text::StringBuilder;
		for each( String^ line in lines )
			text->Append( line )->Append( L'\n' );
		return text->ToString();
	}

	void WriteLines( String^ path, List< String^ >^ lines )
	{
		FixtureFiles::WriteText( path, LinesText( lines ) );
	}

	// SHA-256 of the lines' text as WriteText encodes it (UTF-8, no BOM),
	// before compression, so the hash doesn't depend on the gzip encoder.
	// Fed a line at a time, so a large result isn't copied into one string.
	String^ LinesSha256( List< String^ >^ lines )
	{
		Text::UTF8Encoding^ utf8 = gcnew Text::UTF8Encoding( false );
		Security::Cryptography::SHA256^ sha = Security::Cryptography::SHA256::Create();
		try
		{
			for each( String^ line in lines )
			{
				array< Byte >^ bytes = utf8->GetBytes( line + L"\n" );
				sha->TransformBlock( bytes, 0, bytes->Length, nullptr, 0 );
			}
			sha->TransformFinalBlock( gcnew array< Byte >( 0 ), 0, 0 );
			return Fixtures::HexLower( sha->Hash );
		}
		finally
		{
			delete sha;
		}
	}

	// The harness's own failures, which are never the legacy search's result.
	bool IsHarnessFailure( Exception^ error )
	{
		return dynamic_cast< OutOfMemoryException^ >( error ) != nullptr ||
			   dynamic_cast< InsufficientExecutionStackException^ >( error ) != nullptr;
	}
}

void SearchDump::Run( String^ query_path, String^ out_prefix, const bool write_candidates,
					  const int max_solution_lines, const bool record_exceptions )
{
	JsonObject^ spec = Read( query_path );
	LoadedData^ data = gcnew LoadedData;

	const int illegal_my_charms = LoadMyCharms( GetArray( spec, L"my_charms" ) );
	Query^ query = FormulateQuery( data, spec );
	const int charm_select = CharmSelectIndex( GetString( spec, L"charm_mode" ) );

	JsonWriter^ json = gcnew JsonWriter;
	json->BeginObject();
	json->Field( L"id", GetString( spec, L"id" ) );
	// The query exactly as the harness parsed it, so tests can tell when the
	// corpus file has changed since this golden was generated.
	json->Field( L"query_json", Serialize( spec ) );
	json->Field( L"my_charms_loaded", CharmDatabase::mycharms.Count );
	json->Field( L"my_charms_illegal", illegal_my_charms );

	json->Key( L"relevant_armor_counts" );
	json->BeginArray();
	for( int i = 0; i < query->rel_armor.Count; ++i )
		json->Value( query->rel_armor[ i ]->Count );
	json->EndArray();
	json->Field( L"relevant_decoration_count", query->rel_decorations.Count );

	ResultSet results;
	List< String^ >^ lines = gcnew List< String^ >;
	List< String^ >^ candidates = gcnew List< String^ >;
	Exception^ worker_exception = nullptr;
	int failed_worker = -1;
	List< Charm^ >^ worker_charms = query->skills.Count > 0 ? WorkerCharms( query, charm_select ) : gcnew List< Charm^ >;
	// Workers past a recorded exception don't run, so they're missing from "workers".
	json->Field( L"worker_count", worker_charms->Count );
	json->Key( L"workers" );
	json->BeginArray();
	for( int worker = 0; worker < worker_charms->Count; ++worker )
	{
		Charm^ charm = worker_charms[ worker ];
		List< Solution^ >^ found = nullptr;
		try
		{
			found = RunWorker( query, charm );
		}
		catch( Exception^ error )
		{
			if( !record_exceptions || IsHarnessFailure( error ) )
				throw;
			// In the GUI a throwing worker shows a message box and its result is
			// lost, while results already reported stay, depending on timing
			// (Form1.h:1804-1811). Nothing past the throw is contract, so stop.
			worker_exception = error;
			failed_worker = worker;
			break;
		}
		if( write_candidates )
		{
			for each( Solution^ solution in found )
			{
				String^ charm_name = solution->charm ? solution->charm->GetName() : L"";
				candidates->Add( Convert::ToString( worker ) + L"\t" + charm_name + L"\t" + SolutionLine( solution ) );
			}
		}
		List< Solution^ >^ added = results.AddSolutions( found );
		List< String^ >^ added_lines = gcnew List< String^ >;
		for each( Solution^ solution in added )
			added_lines->Add( SolutionLine( solution ) );
		lines->AddRange( added_lines );
		json->BeginObject();
		json->Field( L"worker", worker );
		// Charm has a member operator==, so "charm == nullptr" would call it: test the handle.
		json->Field( L"charm", charm ? charm->GetName() : nullptr );
		json->Field( L"found", found->Count );
		json->Field( L"added", added->Count );
		json->Field( L"added_sha256", LinesSha256( added_lines ) );
		json->EndObject();
	}
	json->EndArray();

	List< String^ >^ sorted_lines = gcnew List< String^ >( lines );
	sorted_lines->Sort( StringComparer::Ordinal );
	const bool write_solutions = max_solution_lines < 0 || lines->Count <= max_solution_lines;
	json->Field( L"solution_count", lines->Count );
	// Harness order is the contract: which duplicate survives depends on it (quirk 5).
	json->Field( L"solutions_sha256", LinesSha256( lines ) );
	// The same lines sorted ordinally, to tell "same set, different order" apart.
	json->Field( L"solution_set_sha256", LinesSha256( sorted_lines ) );
	json->Field( L"solutions_file", write_solutions );
	if( record_exceptions )
	{
		json->Key( L"exception" );
		if( worker_exception )
		{
			json->BeginObject();
			json->Field( L"worker", failed_worker );
			json->Field( L"type", worker_exception->GetType()->Name );
			json->Field( L"message", worker_exception->Message );
			json->EndObject();
		}
		else
			json->Null();
	}
	json->EndObject();

	json->WriteToFile( out_prefix + L".manifest.json" );
	String^ solutions_path = out_prefix + L".solutions.txt.gz";
	if( write_solutions )
		WriteLines( solutions_path, lines );
	else if( IO::File::Exists( solutions_path ) )
		IO::File::Delete( solutions_path );
	if( write_candidates )
		WriteLines( out_prefix + L".candidates.txt.gz", candidates );
}
