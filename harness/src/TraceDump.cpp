#include "stdafx.h"
#include "TraceDump.h"
#include "Json.h"
#include "LegacySolution.h"
#include "QueryFile.h"
#include "SolutionProbe.h"
#include "Workers.h"
#include "Armor.h"
#include "CharmDatabase.h"
#include "Decoration.h"
#include "LoadedData.h"
#include "Skill.h"
#include "Solution.h"

using namespace System;
using namespace System::Collections::Generic;
using namespace System::Text;

namespace
{
	// Compact JSON fragments: a trace file holds one object per line. Strings
	// are escaped as JsonWriter escapes them.
	String^ Str( String^ text )
	{
		if( text == nullptr )
			return L"null";
		StringBuilder^ sb = gcnew StringBuilder( L"\"" );
		for each( wchar_t c in text )
		{
			if( c == L'"' )
				sb->Append( L"\\\"" );
			else if( c == L'\\' )
				sb->Append( L"\\\\" );
			else if( c < 0x20 || c > 0x7e )
				sb->Append( L"\\u" )->Append( ( (int)c ).ToString( L"x4" ) );
			else
				sb->Append( c );
		}
		return sb->Append( L'"' )->ToString();
	}

	String^ Bool( const bool value )
	{
		return value ? L"true" : L"false";
	}

	String^ DecorationList( List_t< Decoration^ >% decorations )
	{
		StringBuilder^ sb = gcnew StringBuilder( L"[" );
		for( int i = 0; i < decorations.Count; ++i )
		{
			if( i ) sb->Append( L',' );
			sb->Append( decorations[ i ]->index );
		}
		return sb->Append( L']' )->ToString();
	}

	String^ SkillList( List_t< Skill^ >% skills )
	{
		StringBuilder^ sb = gcnew StringBuilder( L"[" );
		for( int i = 0; i < skills.Count; ++i )
		{
			if( i ) sb->Append( L',' );
			sb->Append( Utility::GetIndexOf( %Skill::static_skills, skills[ i ] ) );
		}
		return sb->Append( L']' )->ToString();
	}

	// [[ability, points], ...] in the map's enumeration order.
	String^ AbilityMapJson( AbilityMap% abilities )
	{
		StringBuilder^ sb = gcnew StringBuilder( L"[" );
		bool first = true;
		for each( KeyValuePair< Ability^, int > pair in abilities )
		{
			if( !first ) sb->Append( L',' );
			first = false;
			sb->Append( L'[' )->Append( pair.Key->static_index )->Append( L',' )->Append( pair.Value )->Append( L']' );
		}
		return sb->Append( L']' )->ToString();
	}

	String^ PairsJson( List_t< AbilityPair^ >% pairs )
	{
		StringBuilder^ sb = gcnew StringBuilder( L"[" );
		for( int i = 0; i < pairs.Count; ++i )
		{
			if( i ) sb->Append( L',' );
			sb->Append( L'[' )->Append( pairs[ i ]->ability->static_index )->Append( L',' )->Append( pairs[ i ]->amount )->Append( L']' );
		}
		return sb->Append( L']' )->ToString();
	}

	String^ CharmJson( Charm^ charm )
	{
		// Charm has a member operator==: test the handle, not "charm == nullptr".
		if( !charm )
			return L"null";
		return L"{\"num_slots\":" + Convert::ToString( charm->num_slots ) + L",\"abilities\":" + PairsJson( charm->abilities ) + L"}";
	}

	String^ UnsignedList( array< unsigned >^ values )
	{
		if( !values )
			return L"null";
		StringBuilder^ sb = gcnew StringBuilder( L"[" );
		for( int i = 0; i < values->Length; ++i )
		{
			if( i ) sb->Append( L',' );
			sb->Append( values[ i ] );
		}
		return sb->Append( L']' )->ToString();
	}

	// Every field a stage can change, in a fixed order. Dictionary keeps
	// insertion order while nothing is removed.
	Dictionary< String^, String^ >^ TakeSnapshot( Solution^ sol, CalculationData^ data )
	{
		Dictionary< String^, String^ >^ fields = gcnew Dictionary< String^, String^ >;
		fields->Add( L"decorations", DecorationList( sol->decorations ) );
		fields->Add( L"body_decorations", DecorationList( sol->body_decorations ) );
		fields->Add( L"non_body_decorations", DecorationList( sol->non_body_decorations ) );
		fields->Add( L"abilities", AbilityMapJson( sol->abilities ) );
		fields->Add( L"extra_skills", SkillList( sol->extra_skills ) );
		fields->Add( L"bad_skills", SkillList( sol->bad_skills ) );
		fields->Add( L"charm", CharmJson( sol->charm ) );
		fields->Add( L"torso_slots_spare", Convert::ToString( sol->torso_slots_spare ) );
		fields->Add( L"torso_multiplier", Convert::ToString( sol->torso_multiplier ) );
		fields->Add( L"total_slots_spare", Convert::ToString( sol->total_slots_spare ) );
		fields->Add( L"slots_spare", UnsignedList( sol->slots_spare ) );
		fields->Add( L"need", data ? AbilityMapJson( data->need ) : gcnew String( L"null" ) );
		fields->Add( L"defence", Convert::ToString( sol->defence ) );
		fields->Add( L"max_defence", Convert::ToString( sol->max_defence ) );
		fields->Add( L"rarity", Convert::ToString( sol->rarity ) );
		fields->Add( L"difficulty", Convert::ToString( sol->difficulty ) );
		fields->Add( L"fire_res", Convert::ToString( sol->fire_res ) );
		fields->Add( L"ice_res", Convert::ToString( sol->ice_res ) );
		fields->Add( L"water_res", Convert::ToString( sol->water_res ) );
		fields->Add( L"thunder_res", Convert::ToString( sol->thunder_res ) );
		fields->Add( L"dragon_res", Convert::ToString( sol->dragon_res ) );
		return fields;
	}

	String^ StateKey( Solution^ sol )
	{
		StringBuilder^ sb = gcnew StringBuilder;
		for each( KeyValuePair< String^, String^ > field in TakeSnapshot( sol, LegacySolution::GetData( sol ) ) )
			sb->Append( field.Key )->Append( L'=' )->Append( field.Value )->Append( L';' );
		return sb->ToString();
	}

	// An unsigned counter at or above 2^31 is an underflow that wrapped.
	bool Wrapped( Solution^ sol )
	{
		const unsigned limit = 0x80000000u;
		if( sol->torso_slots_spare >= limit || sol->torso_multiplier >= limit || sol->total_slots_spare >= limit )
			return true;
		if( sol->slots_spare )
		{
			for each( unsigned count in sol->slots_spare )
			{
				if( count >= limit )
					return true;
			}
		}
		return false;
	}

	// Records each stage as the fields that changed since the previous one
	// (all fields for complete stages). Tracks wrapped counters either way.
	ref class StageRecorder
	{
	public:
		StageRecorder( const bool record )
			: record( record ), wrapped( false ), stages( gcnew List< String^ > ), previous( nullptr )
		{}

		bool wrapped;
		List< String^ >^ stages;

		void Stage( String^ name, Solution^ sol, CalculationData^ data, const bool complete, String^ result )
		{
			wrapped = wrapped || Wrapped( sol );
			if( !record )
				return;
			Dictionary< String^, String^ >^ current = TakeSnapshot( sol, data );
			StringBuilder^ sb = gcnew StringBuilder;
			sb->Append( L"{\"stage\":" )->Append( Str( name ) );
			if( result )
				sb->Append( L',' )->Append( result );
			for each( KeyValuePair< String^, String^ > field in current )
			{
				if( complete || !previous || !String::Equals( previous[ field.Key ], field.Value ) )
					sb->Append( L',' )->Append( Str( field.Key ) )->Append( L':' )->Append( field.Value );
			}
			stages->Add( sb->Append( L'}' )->ToString() );
			previous = current;
		}

	private:
		bool record;
		Dictionary< String^, String^ >^ previous;
	};

	ref struct StepResult
	{
		String^ outcome;
		bool via_fix_bad, via_reorder, decorations_fell;

		StepResult() : outcome( nullptr ), via_fix_bad( false ), via_reorder( false ), decorations_fell( false ) {}
	};

	// Solution::MatchesQuery, Solution.cpp:660-724, line for line, with a stage
	// after each step. CheckBadSkills' short-circuit (:112-115) is unrolled so
	// its two repairs are separate stages. The Assert calls and the _DEBUG
	// block compile to nothing in the Release build and are left out.
	StepResult^ RunStepped( Solution^ sol, Query^ query, StageRecorder^ recorder )
	{
		StepResult^ result = gcnew StepResult;
		CalculationData^ data = LegacySolution::NewData( sol, query );
		LegacySolution::SetData( sol, data );

		GetInitialData( data );
		recorder->Stage( L"initial", sol, data, true, nullptr );
		CalculateDecorations< true, true >( data );
		recorder->Stage( L"decorated", sol, data, false, nullptr );

		bool enough = true;
		for each( Skill^ skill in query->skills )
		{
			const int have = sol->abilities[ skill->ability ],
					  need = data->need[ skill->ability ];
			if( have < need )
			{
				enough = false;
				break;
			}
		}
		recorder->Stage( L"points", sol, data, false, L"\"accepted\":" + Bool( enough ) );
		if( !enough )
		{
			result->outcome = L"rejected_points";
			return result;
		}

		LegacySolution::Call( sol, L"CalculateExtraSkills" );
		recorder->Stage( L"extra", sol, data, false, nullptr );

		if( !query->allow_bad && sol->bad_skills.Count > 0 )
		{
			const bool called = sol->total_slots_spare > 0;
			const bool fixed = called && LegacySolution::CallBool( sol, L"FixBadSkills" );
			recorder->Stage( L"fix_bad", sol, data, false, L"\"called\":" + Bool( called ) + L",\"result\":" + Bool( fixed ) );
			bool reordered = false;
			if( !fixed )
			{
				reordered = LegacySolution::CallBool( sol, L"ReorderGems" );
				recorder->Stage( L"reorder", sol, data, false, L"\"result\":" + Bool( reordered ) );
			}
			if( !fixed && !reordered )
			{
				result->outcome = L"rejected_bad_skills";
				return result;
			}
			result->via_fix_bad = fixed;
			result->via_reorder = reordered;
		}

		if( sol->charm )
		{
			if( sol->charm->custom )
			{
				const int before = sol->decorations.Count;
				LegacySolution::Call( sol, L"RearrangeDecorations" );
				result->decorations_fell = sol->decorations.Count < before;
				recorder->Stage( L"rearranged", sol, data, false, nullptr );
			}
			else
			{
				LegacySolution::Call( sol, L"ReduceSlots" );
				recorder->Stage( L"slots_reduced", sol, data, false, nullptr );
				LegacySolution::Call( sol, L"ReduceSkills" );
				recorder->Stage( L"skills_reduced", sol, data, false, nullptr );
				const int before = sol->decorations.Count;
				LegacySolution::Call( sol, L"RearrangeDecorations" );
				result->decorations_fell = sol->decorations.Count < before;
				recorder->Stage( L"rearranged", sol, data, false, nullptr );
				LegacySolution::Call( sol, L"ReduceCharm" );
				recorder->Stage( L"charm_reduced", sol, data, false, nullptr );
				LegacySolution::Call( sol, L"CalculateExtraSkills" );
				recorder->Stage( L"extra_final", sol, data, false, nullptr );
			}
		}

		sol->slots_spare[ sol->torso_slots_spare ]++;
		for each( Decoration^ deco in sol->decorations )
		{
			sol->difficulty += deco->difficulty;
		}
		recorder->Stage( L"final", sol, data, true, nullptr );
		result->outcome = L"accepted";
		return result;
	}

	// One job as Form1::backgroundWorker1_DoWork builds it (Form1.h:1904-1912).
	Solution^ NewJob( array< Armor^ >^ armors, Charm^ charm_template )
	{
		Solution^ job = gcnew Solution();
		for each( Armor^ armor in armors )
			job->armors.Add( armor );
		job->charm = charm_template ? gcnew Charm( charm_template ) : nullptr;
		return job;
	}

	ref struct Outcome
	{
		StepResult^ step;
		String^ exception;
		StageRecorder^ recorder;
		Solution^ solution;
	};

	Outcome^ Step( array< Armor^ >^ armors, Charm^ charm_template, Query^ query, const bool record )
	{
		Outcome^ outcome = gcnew Outcome;
		outcome->solution = NewJob( armors, charm_template );
		outcome->recorder = gcnew StageRecorder( record );
		try
		{
			outcome->step = RunStepped( outcome->solution, query, outcome->recorder );
		}
		catch( Exception^ error )
		{
			outcome->exception = error->GetType()->Name;
		}
		return outcome;
	}

	// Runs the real MatchesQuery and throws if the stepped copy disagrees.
	void CheckAgainstReal( array< Armor^ >^ armors, Charm^ charm_template, Query^ query, Outcome^ stepped )
	{
		Solution^ real = NewJob( armors, charm_template );
		bool accepted = false;
		String^ exception = nullptr;
		try
		{
			accepted = real->MatchesQuery( query );
		}
		catch( Exception^ error )
		{
			exception = error->GetType()->Name;
		}
		const bool stepped_accepted = stepped->step && String::Equals( stepped->step->outcome, L"accepted" );
		if( !String::Equals( exception, stepped->exception ) || accepted != stepped_accepted ||
			!String::Equals( StateKey( real ), StateKey( stepped->solution ) ) )
		{
			throw gcnew InvalidOperationException( L"The stepped MatchesQuery disagrees with the original" );
		}
	}

	array< String^ >^ CensusKeys()
	{
		array< String^ >^ keys = {
			L"accepted", L"rejected_points", L"rejected_bad_skills", L"exception",
			L"via_fix_bad", L"via_reorder", L"with_bad_skills", L"charm_changed",
			L"charm_nulled", L"decorations_fell", L"wrapped" };
		return keys;
	}

	// The census categories one combination falls in, in CensusKeys order,
	// then "exception:<type>".
	List< String^ >^ Categories( Outcome^ outcome, Charm^ charm_template )
	{
		List< String^ >^ categories = gcnew List< String^ >;
		if( outcome->exception )
			categories->Add( L"exception" );
		else
			categories->Add( outcome->step->outcome );
		const bool accepted = !outcome->exception && String::Equals( outcome->step->outcome, L"accepted" );
		Solution^ sol = outcome->solution;
		if( accepted && outcome->step->via_fix_bad ) categories->Add( L"via_fix_bad" );
		if( accepted && outcome->step->via_reorder ) categories->Add( L"via_reorder" );
		if( accepted && sol->bad_skills.Count > 0 ) categories->Add( L"with_bad_skills" );
		if( accepted && charm_template && !String::Equals( CharmJson( sol->charm ), CharmJson( charm_template ) ) )
			categories->Add( L"charm_changed" );
		if( accepted && charm_template && !sol->charm ) categories->Add( L"charm_nulled" );
		if( outcome->step && outcome->step->decorations_fell ) categories->Add( L"decorations_fell" );
		if( outcome->recorder->wrapped ) categories->Add( L"wrapped" );
		if( outcome->exception ) categories->Add( L"exception:" + outcome->exception );
		return categories;
	}

	String^ IntList( array< int >^ values )
	{
		StringBuilder^ sb = gcnew StringBuilder( L"[" );
		for( int i = 0; i < values->Length; ++i )
		{
			if( i ) sb->Append( L',' );
			sb->Append( values[ i ] );
		}
		return sb->Append( L']' )->ToString();
	}

	String^ ComboKey( const int worker, array< int >^ combination )
	{
		return Convert::ToString( worker ) + L":" + IntList( combination );
	}

	HashSet< String^ >^ IncludedCombinations( QueryFile::JsonObject^ spec )
	{
		HashSet< String^ >^ included = gcnew HashSet< String^ >;
		if( !spec->ContainsKey( L"include" ) )
			return included;
		for each( Object^ item in QueryFile::GetArray( spec, L"include" ) )
		{
			array< Object^ >^ entry = safe_cast< array< Object^ >^ >( item );
			if( entry->Length != 6 )
				throw gcnew FormatException( L"include entries are [worker, head, body, arms, waist, legs]" );
			array< int >^ combination = gcnew array< int >( 5 );
			for( int i = 0; i < 5; ++i )
				combination[ i ] = Convert::ToInt32( entry[ i + 1 ] );
			included->Add( ComboKey( Convert::ToInt32( entry[ 0 ] ), combination ) );
		}
		return included;
	}

	String^ StringList( List< String^ >^ values )
	{
		StringBuilder^ sb = gcnew StringBuilder( L"[" );
		for( int i = 0; i < values->Count; ++i )
		{
			if( i ) sb->Append( L',' );
			sb->Append( Str( values[ i ] ) );
		}
		return sb->Append( L']' )->ToString();
	}

	String^ CountsJson( Dictionary< String^, int >^ counts )
	{
		StringBuilder^ sb = gcnew StringBuilder( L"{" );
		bool first = true;
		for each( KeyValuePair< String^, int > pair in counts )
		{
			if( !first ) sb->Append( L',' );
			first = false;
			sb->Append( Str( pair.Key ) )->Append( L':' )->Append( pair.Value );
		}
		return sb->Append( L'}' )->ToString();
	}
}

String^ TraceDump::QueryPath( String^ spec_path )
{
	String^ query = QueryFile::GetString( QueryFile::Read( spec_path ), L"query" );
	return IO::Path::GetFullPath( IO::Path::Combine( IO::Path::GetDirectoryName( spec_path ), query ) );
}

void TraceDump::Run( String^ spec_path, String^ out_path )
{
	const int sample_everything_up_to = 500, default_samples = 150, firsts_per_category = 2;

	QueryFile::JsonObject^ spec = QueryFile::Read( spec_path );
	QueryFile::JsonObject^ query_spec = QueryFile::Read( QueryPath( spec_path ) );
	HashSet< String^ >^ included = IncludedCombinations( spec );

	LoadedData^ data = gcnew LoadedData;
	const int illegal_my_charms = Workers::LoadMyCharms( QueryFile::GetArray( query_spec, L"my_charms" ) );
	Query^ query = QueryFile::FormulateQuery( data, query_spec );
	const int charm_select = Workers::CharmSelectIndex( QueryFile::GetString( query_spec, L"charm_mode" ) );
	List< Charm^ >^ worker_charms = query->skills.Count > 0 ? Workers::WorkerCharms( query, charm_select ) : gcnew List< Charm^ >;

	// backgroundWorker1_DoWork gives an empty slot one nullptr piece
	// (Form1.h:1865-1869), changing the query for every later reader.
	for each( List_t< Armor^ >^ slot in query->rel_armor )
	{
		if( slot->Count == 0 )
			slot->Add( nullptr );
	}
	List_t< Armor^ >^ head  = query->rel_armor[ int( Armor::ArmorType::HEAD ) ];
	List_t< Armor^ >^ body  = query->rel_armor[ int( Armor::ArmorType::BODY ) ];
	List_t< Armor^ >^ arms  = query->rel_armor[ int( Armor::ArmorType::ARMS ) ];
	List_t< Armor^ >^ waist = query->rel_armor[ int( Armor::ArmorType::WAIST ) ];
	List_t< Armor^ >^ legs  = query->rel_armor[ int( Armor::ArmorType::LEGS ) ];
	const int combinations = head->Count * body->Count * arms->Count * waist->Count * legs->Count;

	List< String^ >^ lines = gcnew List< String^ >;
	List< String^ >^ worker_entries = gcnew List< String^ >;
	for( int worker = 0; worker < worker_charms->Count; ++worker )
	{
		Charm^ charm_template = worker_charms[ worker ];
		int stride = 1;
		if( combinations > sample_everything_up_to )
		{
			stride = spec->ContainsKey( L"stride" ) ? QueryFile::GetInt( spec, L"stride" ) : Math::Max( 1, combinations / default_samples );
		}

		Dictionary< String^, int >^ census = gcnew Dictionary< String^, int >;
		for each( String^ key in CensusKeys() )
			census->Add( key, 0 );
		Dictionary< String^, int >^ exception_types = gcnew Dictionary< String^, int >;
		Dictionary< String^, int >^ seen = gcnew Dictionary< String^, int >;

		int index = 0;
		for( int i = 0; i < head->Count; ++i )
		for( int j = 0; j < body->Count; ++j )
		for( int k = 0; k < arms->Count; ++k )
		for( int l = 0; l < waist->Count; ++l )
		for( int m = 0; m < legs->Count; ++m, ++index )
		{
			array< Armor^ >^ armors = { head[ i ], body[ j ], arms[ k ], waist[ l ], legs[ m ] };
			array< int >^ combination = { i, j, k, l, m };

			Outcome^ outcome = Step( armors, charm_template, query, false );
			CheckAgainstReal( armors, charm_template, query, outcome );

			List< String^ >^ sampled_by = gcnew List< String^ >;
			if( stride == 1 || index % stride == 0 )
				sampled_by->Add( stride == 1 ? L"all" : L"stride" );
			for each( String^ category in Categories( outcome, charm_template ) )
			{
				if( census->ContainsKey( category ) )
					census[ category ]++;
				else if( category->StartsWith( L"exception:" ) )
				{
					String^ type = category->Substring( 10 );
					if( exception_types->ContainsKey( type ) )
						exception_types[ type ]++;
					else
						exception_types->Add( type, 1 );
				}
				const int count = seen->ContainsKey( category ) ? seen[ category ] : 0;
				if( count < firsts_per_category )
					sampled_by->Add( L"first:" + category );
				seen[ category ] = count + 1;
			}
			if( included->Remove( ComboKey( worker, combination ) ) )
				sampled_by->Add( L"include" );
			if( sampled_by->Count == 0 )
				continue;

			Outcome^ traced = Step( armors, charm_template, query, true );
			array< int >^ armor_indices = gcnew array< int >( 5 );
			for( int slot = 0; slot < 5; ++slot )
				armor_indices[ slot ] = armors[ slot ] ? int( armors[ slot ]->index ) : -1;
			lines->Add(
				L"{\"worker\":" + Convert::ToString( worker ) +
				L",\"combination\":" + IntList( combination ) +
				L",\"index\":" + Convert::ToString( index ) +
				L",\"armor\":" + IntList( armor_indices ) +
				L",\"sampled_by\":" + StringList( sampled_by ) +
				L",\"outcome\":" + Str( traced->exception ? gcnew String( L"exception" ) : traced->step->outcome ) +
				L",\"exception\":" + Str( traced->exception ) +
				L",\"stages\":[" + String::Join( L",", traced->recorder->stages ) + L"]}" );
		}

		worker_entries->Add(
			L"{\"worker\":" + Convert::ToString( worker ) +
			L",\"charm\":" + Str( charm_template ? charm_template->GetName() : nullptr ) +
			L",\"template\":" + CharmJson( charm_template ) +
			L",\"combinations\":" + Convert::ToString( combinations ) +
			L",\"stride\":" + Convert::ToString( stride ) +
			L",\"census\":" + CountsJson( census ) +
			L",\"exception_types\":" + CountsJson( exception_types ) + L"}" );
	}

	if( included->Count > 0 )
		throw gcnew FormatException( L"include names a combination the search never runs: " + String::Join( L" ", included ) );

	StringBuilder^ deco_map = gcnew StringBuilder( L"[" );
	for( unsigned size = 0; size < 4; ++size )
	{
		if( size ) deco_map->Append( L',' );
		deco_map->Append( L'[' );
		bool first = true;
		for each( Decoration^ deco in query->rel_decorations )
		{
			if( deco->slots_required != size ) continue;
			if( !first ) deco_map->Append( L',' );
			first = false;
			deco_map->Append( deco->index );
		}
		deco_map->Append( L']' );
	}
	deco_map->Append( L']' );

	String^ header =
		L"{\"id\":" + Str( IO::Path::GetFileNameWithoutExtension( spec_path ) ) +
		L",\"query_json\":" + Str( QueryFile::Serialize( query_spec ) ) +
		L",\"spec_json\":" + Str( QueryFile::Serialize( spec ) ) +
		L",\"my_charms_illegal\":" + Convert::ToString( illegal_my_charms ) +
		L",\"rel_decoration_map\":" + deco_map->ToString() +
		L",\"point_score_rank\":" + IntList( SolutionProbe::PointScoreRanks( 23 ) ) +
		L",\"workers\":[" + String::Join( L",", worker_entries ) + L"]}";

	StringBuilder^ text = gcnew StringBuilder( header );
	text->Append( L'\n' );
	for each( String^ line in lines )
		text->Append( line )->Append( L'\n' );
	FixtureFiles::WriteText( out_path, text->ToString() );
}
