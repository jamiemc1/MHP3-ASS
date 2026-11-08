#include "stdafx.h"
#include "SearchDump.h"
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

		int AddSolutions( List_t< Solution^ >^ solutions )
		{
			const int before = all_solutions.Count;
			for each( Solution^ sol in solutions )
			{
				if( sol->charm )
					AddSolution( sol->charm->GetName(), sol );
				else
				{
					all_solutions.Add( sol );
				}
			}
			return all_solutions.Count - before;
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

		void AddSolution( String^ charm, Solution^ sol )
		{
			if( SolutionExists( charm, sol ) ) return;
			all_solutions.Add( sol );
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

	void WriteLines( String^ path, List< String^ >^ lines )
	{
		Text::StringBuilder^ text = gcnew Text::StringBuilder;
		for each( String^ line in lines )
			text->Append( line )->Append( L'\n' );
		FixtureFiles::WriteText( path, text->ToString() );
	}
}

void SearchDump::Run( String^ query_path, String^ out_prefix, bool write_candidates )
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
	List< String^ >^ candidates = gcnew List< String^ >;
	List< Charm^ >^ worker_charms = query->skills.Count > 0 ? WorkerCharms( query, charm_select ) : gcnew List< Charm^ >;
	json->Key( L"workers" );
	json->BeginArray();
	for( int worker = 0; worker < worker_charms->Count; ++worker )
	{
		Charm^ charm = worker_charms[ worker ];
		List< Solution^ >^ found = RunWorker( query, charm );
		if( write_candidates )
		{
			for each( Solution^ solution in found )
			{
				String^ charm_name = solution->charm ? solution->charm->GetName() : L"";
				candidates->Add( Convert::ToString( worker ) + L"\t" + charm_name + L"\t" + SolutionLine( solution ) );
			}
		}
		const int added = results.AddSolutions( found );
		json->BeginObject();
		json->Field( L"worker", worker );
		// Charm has a member operator==, so "charm == nullptr" would call it: test the handle.
		json->Field( L"charm", charm ? charm->GetName() : nullptr );
		json->Field( L"found", found->Count );
		json->Field( L"added", added );
		json->EndObject();
	}
	json->EndArray();

	List< String^ >^ lines = gcnew List< String^ >;
	for each( Solution^ solution in results.all_solutions )
		lines->Add( SolutionLine( solution ) );
	json->Field( L"solution_count", lines->Count );
	json->EndObject();

	json->WriteToFile( out_prefix + L".manifest.json" );
	WriteLines( out_prefix + L".solutions.txt.gz", lines );
	if( write_candidates )
		WriteLines( out_prefix + L".candidates.txt.gz", candidates );
}
