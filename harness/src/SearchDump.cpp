#include "stdafx.h"
#include "SearchDump.h"
#include "Json.h"
#include "Armor.h"
#include "CharmDatabase.h"
#include "Decoration.h"
#include "LoadedData.h"
#include "Skill.h"
#include "Solution.h"

using namespace System;
using namespace System::Collections::Generic;

namespace
{
	typedef Dictionary< String^, Object^ > JsonObject;

	JsonObject^ ReadQueryFile( String^ path )
	{
		Web::Script::Serialization::JavaScriptSerializer^ serializer = gcnew Web::Script::Serialization::JavaScriptSerializer;
		serializer->MaxJsonLength = Int32::MaxValue;
		return safe_cast< JsonObject^ >( serializer->DeserializeObject( IO::File::ReadAllText( path ) ) );
	}

	int GetInt( JsonObject^ spec, String^ key ) { return Convert::ToInt32( spec[ key ] ); }
	bool GetBool( JsonObject^ spec, String^ key ) { return Convert::ToBoolean( spec[ key ] ); }
	String^ GetString( JsonObject^ spec, String^ key ) { return safe_cast< String^ >( spec[ key ] ); }
	array< Object^ >^ GetArray( JsonObject^ spec, String^ key ) { return safe_cast< array< Object^ >^ >( spec[ key ] ); }

	// Form1::FormulateQuery( false, use_gunner_skills ), Form1.h:1184-1216, with
	// the form's controls replaced by corpus fields. Skills are indices into
	// Skill::static_skills, as the GUI saves them.
	Query^ FormulateQuery( LoadedData^ data, JsonObject^ spec )
	{
		Query^ query = gcnew Query;
		for( int i = 0; i < int( Armor::ArmorType::NumArmorTypes ); ++i )
		{
			query->rel_armor.Add( gcnew List_t< Armor^ >() );
			query->inf_armor.Add( gcnew List_t< Armor^ >() );
		}
		query->weapon_slots_allowed = GetInt( spec, L"weapon_slots" );
		query->elder_star = GetInt( spec, L"elder_star" );
		query->hr = GetInt( spec, L"hr" );

		String^ gender = GetString( spec, L"gender" );
		if( gender != L"male" && gender != L"female" )
			throw gcnew FormatException( L"gender must be male or female, got " + gender );
		query->gender = gender == L"male" ? Gender::MALE : Gender::FEMALE;

		String^ hunter_type = GetString( spec, L"hunter_type" );
		if( hunter_type != L"blademaster" && hunter_type != L"gunner" )
			throw gcnew FormatException( L"hunter_type must be blademaster or gunner, got " + hunter_type );
		query->hunter_type = hunter_type == L"blademaster" ? HunterType::BLADEMASTER : HunterType::GUNNER;

		query->include_piercings = GetBool( spec, L"include_piercings" );
		query->allow_bad = GetBool( spec, L"allow_bad" );
		query->allow_event = GetBool( spec, L"allow_event" );
		query->allow_low_rank = GetBool( spec, L"allow_low_rank" );

		array< Object^ >^ skills = GetArray( spec, L"skills" );
		array< Object^ >^ skill_names = GetArray( spec, L"skill_names" );
		if( skills->Length != skill_names->Length )
			throw gcnew FormatException( L"skills and skill_names must be the same length" );
		// Only queries the GUI could build: at most NumSkills (6) drop-downs
		// (Form1.h:95), each offering skills with positive points
		// (InitSkills, :224-247) and excluding abilities already chosen (:1527-1537).
		if( skills->Length > 6 )
			throw gcnew FormatException( L"The GUI allows at most 6 skills" );
		for( int i = 0; i < skills->Length; ++i )
		{
			const unsigned index = Convert::ToUInt32( skills[ i ] );
			if( index >= unsigned( Skill::static_skills.Count ) )
				throw gcnew FormatException( L"skill index " + Convert::ToString( index ) + L" out of range" );
			Skill^ skill = data->FindSkill( index );
			// Names are for readers; the index is what the GUI uses. Catch typos early.
			String^ expected_name = Convert::ToString( skill_names[ i ] );
			if( skill->name != expected_name )
				throw gcnew FormatException( L"skill " + Convert::ToString( index ) + L" is \"" + skill->name + L"\", not \"" + expected_name + L"\"" );
			if( skill->points_required <= 0 )
				throw gcnew FormatException( L"skill \"" + skill->name + L"\" has no positive points; the GUI does not offer it" );
			for each( Skill^ chosen in query->skills )
			{
				if( chosen->ability == skill->ability )
					throw gcnew FormatException( L"skills \"" + chosen->name + L"\" and \"" + skill->name + L"\" share an ability; the GUI allows one per ability" );
			}
			query->skills.Add( skill );
		}
		data->GetRelevantData( query );
		return query;
	}

	// CharmDatabase::LoadCustom(), CharmDatabase.cpp:108-168, reading the lines
	// from the corpus instead of Data/mycharms.txt. Malformed lines throw
	// instead of showing a message box; illegal charms are skipped and counted,
	// as the GUI skips them.
	int LoadMyCharms( array< Object^ >^ lines )
	{
		CharmDatabase::mycharms.Clear();
		int illegal = 0;
		for each( Object^ item in lines )
		{
			String^ temp = safe_cast< String^ >( item );
			if( temp == L"" || temp[ 0 ] == L'#' ) continue;
			List_t< String^ > split;
			Utility::SplitString( %split, temp, L',' );
			if( split.Count != 5 )
				throw gcnew FormatException( L"Incorrect number of commas: " + temp );
			Charm^ charm = gcnew Charm();
			charm->num_slots = Convert::ToUInt32( split[ 0 ] );
			if( split[ 1 ] != L"" )
			{
				Ability^ ab = Ability::FindAbility( split[ 1 ] );
				if( !ab )
					throw gcnew FormatException( L"\"" + split[ 1 ] + L"\": No such skill in " + temp );
				charm->abilities.Add( gcnew AbilityPair( ab, Convert::ToInt32( split[ 2 ] ) ) );
			}
			if( split[ 3 ] != L"" )
			{
				Ability^ ab = Ability::FindAbility( split[ 3 ] );
				if( !ab )
					throw gcnew FormatException( L"\"" + split[ 3 ] + L"\": No such skill in " + temp );
				charm->abilities.Add( gcnew AbilityPair( ab, Convert::ToInt32( split[ 4 ] ) ) );
			}
			if( CharmExists( charm ) ||
				!CharmIsIllegal( charm ) )
			{
				charm->custom = true;
				CharmDatabase::mycharms.Add( charm );
			}
			else illegal++;
		}
		return illegal;
	}

	// Form1::AddCharmToOptimalList, Form1.h:1237-1249.
	void AddCharmToOptimalList( List_t< Charm^ >% lst, Charm^ new_charm )
	{
		for( int i = 0; i < lst.Count; ++i )
		{
			Charm^ curr_charm = lst[ i ];
			if( new_charm->StrictlyBetterThan( curr_charm ) )
				lst.RemoveAt( i-- );
			else if( curr_charm->StrictlyBetterThan( new_charm ) ||
					 curr_charm->BasicallyTheSameAs( new_charm ) )
				return;
		}
		lst.Add( new_charm );
	}

	int CharmSelectIndex( String^ charm_mode )
	{
		array< String^ >^ modes = { L"none", L"my_charms", L"slotted", L"one_skill", L"two_skill" };
		const int index = Array::IndexOf( modes, charm_mode );
		if( index < 0 )
			throw gcnew FormatException( L"charm_mode must be one of none, my_charms, slotted, one_skill, two_skill; got " + charm_mode );
		return index;
	}

	// The charm template of each worker Form1::StartSearch starts, in start order
	// (Form1.h:1273-1373). A nullptr entry is a worker searching without a charm.
	List< Charm^ >^ WorkerCharms( Query^ query, const int charm_select )
	{
		List< Charm^ >^ workers = gcnew List< Charm^ >;

		//Check for Auto-Guard first
		if( charm_select > 1 )
		{
			for each( Ability^ ab in query->rel_abilities )
			{
				if( ab->auto_guard )
				{
					for each( Charm^ ch in CharmDatabase::mycharms )
					{
						if( ch->abilities.Count == 1 && ch->abilities[ 0 ]->ability == ab )
						{
							workers->Add( ch );
							break;
						}
					}
					return workers;
				}
			}
		}

		switch( charm_select )
		{
		case 0: // no charms
			workers->Add( nullptr );
			break;
		case 1: // my charms only
			{
				List_t< Charm^ > to_search;
				for each( Charm^ ct in CharmDatabase::mycharms )
				{
					AddCharmToOptimalList( to_search, ct );
				}
				workers->Add( nullptr );
				for each( Charm^ ct in to_search )
				{
					workers->Add( ct );
				}
			}
			break;
		case 2: // slotted charms only
			workers->Add( gcnew Charm( 3 ) );
			break;
		case 3: // one skill charms
			for each( Charm^ ct in CharmDatabase::GetCharms( query, false ) )
				workers->Add( ct );
			break;
		case 4: // two skill charms
			for each( Charm^ ct in CharmDatabase::GetCharms( query, true ) )
				workers->Add( ct );
			break;
		}
		return workers;
	}

	// Form1::backgroundWorker1_DoWork, Form1.h:1852-1930, without progress
	// reporting or cancellation. The GUI hands solutions over in batches, but
	// always in this order.
	List< Solution^ >^ RunWorker( Query^ query, Charm^ charm_template )
	{
		List< Solution^ >^ solutions = gcnew List< Solution^ >;
		List_t< Armor^ >^ head  = query->rel_armor[ int( Armor::ArmorType::HEAD ) ];
		List_t< Armor^ >^ body  = query->rel_armor[ int( Armor::ArmorType::BODY ) ];
		List_t< Armor^ >^ arms  = query->rel_armor[ int( Armor::ArmorType::ARMS ) ];
		List_t< Armor^ >^ waist = query->rel_armor[ int( Armor::ArmorType::WAIST ) ];
		List_t< Armor^ >^ legs  = query->rel_armor[ int( Armor::ArmorType::LEGS ) ];

		if( head->Count  == 0 ) head->Add( nullptr );
		if( body->Count  == 0 ) body->Add( nullptr );
		if( arms->Count  == 0 ) arms->Add( nullptr );
		if( waist->Count == 0 ) waist->Add( nullptr );
		if( legs->Count  == 0 ) legs->Add( nullptr );

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
							Solution^ job = gcnew Solution();
							job->armors.Add( head[ i ] );
							job->armors.Add( body[ j ] );
							job->armors.Add( arms[ k ] );
							job->armors.Add( waist[ l ] );
							job->armors.Add( legs[ m ] );
							job->charm = charm_template ? gcnew Charm( charm_template ) : nullptr;

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

String^ SearchDump::QueryLanguage( String^ query_path )
{
	return GetString( ReadQueryFile( query_path ), L"language" );
}

void SearchDump::Run( String^ query_path, String^ out_prefix, bool write_candidates )
{
	JsonObject^ spec = ReadQueryFile( query_path );
	LoadedData^ data = gcnew LoadedData;

	const int illegal_my_charms = LoadMyCharms( GetArray( spec, L"my_charms" ) );
	Query^ query = FormulateQuery( data, spec );
	const int charm_select = CharmSelectIndex( GetString( spec, L"charm_mode" ) );

	JsonWriter^ json = gcnew JsonWriter;
	json->BeginObject();
	json->Field( L"id", GetString( spec, L"id" ) );
	// The query exactly as the harness parsed it, so tests can tell when the
	// corpus file has changed since this golden was generated.
	json->Field( L"query_json", ( gcnew Web::Script::Serialization::JavaScriptSerializer )->Serialize( spec ) );
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
