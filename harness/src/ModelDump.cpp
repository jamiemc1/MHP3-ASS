#include "stdafx.h"
#include "ModelDump.h"
#include "Fixtures.h"
#include "Armor.h"
#include "CharmDatabase.h"
#include "Decoration.h"
#include "Skill.h"

using namespace System;
using namespace System::Collections::Generic;

namespace
{
	const int MinSkillPoints = -40;
	const int MaxSkillPoints = 60;

	// Ability::GetSkill (Skill.cpp:9-29) for every ability, over a points
	// range wider than any search reaches. -1 for no skill.
	void WriteSkillThresholds( JsonWriter^ json )
	{
		json->Key( L"get_skill" );
		json->BeginObject();
		json->Field( L"min_points", MinSkillPoints );
		json->Field( L"max_points", MaxSkillPoints );
		json->Key( L"skills" );
		json->BeginArray();
		for each( Ability^ ability in Ability::static_abilities )
		{
			json->BeginArray();
			for( int points = MinSkillPoints; points <= MaxSkillPoints; ++points )
			{
				Skill^ skill = ability->GetSkill( points );
				json->Value( skill ? Utility::GetIndexOf( %Skill::static_skills, skill ) : -1 );
			}
			json->EndArray();
		}
		json->EndArray();
		json->EndObject();
	}

	// Decoration::IsBetterThan (Decoration.cpp:95-102), which also covers the
	// file-local NotWorse. Row i, character j is '1' when decoration i is
	// better than decoration j. Its rel_abilities argument is unused.
	void WriteDecorationComparisons( JsonWriter^ json )
	{
		List< Ability^ >^ unused = gcnew List< Ability^ >;
		json->Key( L"decoration_is_better_than" );
		json->BeginArray();
		for each( Decoration^ decoration in Decoration::static_decorations )
		{
			Text::StringBuilder^ row = gcnew Text::StringBuilder;
			for each( Decoration^ other in Decoration::static_decorations )
				row->Append( decoration->IsBetterThan( other, unused ) ? L'1' : L'0' );
			json->Value( row->ToString() );
		}
		json->EndArray();
	}

	Charm^ MakeCharm( const unsigned slots, Ability^ ability1, const int points1, Ability^ ability2, const int points2 )
	{
		Charm^ charm = gcnew Charm( slots );
		if( ability1 )
			charm->abilities.Add( gcnew AbilityPair( ability1, points1 ) );
		if( ability2 )
			charm->abilities.Add( gcnew AbilityPair( ability2, points2 ) );
		return charm;
	}

	// A deterministic sample around the generated charms: each one as it is
	// and nudged past what the game can produce. Slots stay at 3 or fewer:
	// CharmIsIllegal indexes table_hashes by slot count.
	List< Charm^ >^ ValidityCases()
	{
		List< Charm^ >^ cases = gcnew List< Charm^ >;
		for( unsigned slots = 0; slots < 4; ++slots )
			cases->Add( MakeCharm( slots, nullptr, 0, nullptr, 0 ) );

		unsigned entry_number = 0;
		for( int charm_type = 0; charm_type < CharmDatabase::table->GetLength( 0 ); ++charm_type )
		{
			for( unsigned slots = 0; slots < 4; ++slots )
			{
				for each( KeyValuePair< Ability^, unsigned > entry in CharmDatabase::table[ charm_type, slots ] )
				{
					if( entry_number++ % 3 != 0 )
						continue;
					const int points = entry.Value;
					cases->Add( MakeCharm( slots, entry.Key, points, nullptr, 0 ) );
					cases->Add( MakeCharm( slots, entry.Key, points + 1, nullptr, 0 ) );
					if( slots < 3 )
						cases->Add( MakeCharm( slots + 1, entry.Key, points, nullptr, 0 ) );
				}
			}
		}

		unsigned pair_number = 0;
		for( int i = 1; i < Ability::static_abilities.Count; ++i )
		{
			for( int j = 0; j < i; ++j )
			{
				List< Charm^ >^ charms = CharmDatabase::table2[ Ability::static_abilities[ i ] ][ Ability::static_abilities[ j ] ];
				if( charms->Count == 0 || pair_number++ % 25 != 0 )
					continue;
				Charm^ charm = charms[ 0 ];
				Ability^ a1 = charm->abilities[ 0 ]->ability;
				Ability^ a2 = charm->abilities[ 1 ]->ability;
				const int p1 = charm->abilities[ 0 ]->amount;
				const int p2 = charm->abilities[ 1 ]->amount;
				cases->Add( MakeCharm( charm->num_slots, a1, p1, a2, p2 ) );
				cases->Add( MakeCharm( charm->num_slots, a2, p2, a1, p1 ) );
				cases->Add( MakeCharm( charm->num_slots, a1, p1 + 1, a2, p2 ) );
				cases->Add( MakeCharm( charm->num_slots, a1, p1, a2, p2 + 1 ) );
				cases->Add( MakeCharm( charm->num_slots, a1, p1, a2, -p2 ) );
				if( charm->num_slots < 3 )
					cases->Add( MakeCharm( charm->num_slots + 1, a1, p1, a2, p2 ) );
			}
		}

		for each( Ability^ ability in Ability::static_abilities )
		{
			if( ability->auto_guard )
			{
				cases->Add( MakeCharm( 0, ability, 10, nullptr, 0 ) );
				cases->Add( MakeCharm( 0, ability, 9, nullptr, 0 ) );
				break;
			}
		}

		// A negative first skill: CharmIsIllegal holds it as unsigned.
		Ability^ first = Ability::static_abilities[ 0 ];
		Ability^ second = Ability::static_abilities[ 1 ];
		cases->Add( MakeCharm( 1, first, -3, nullptr, 0 ) );
		cases->Add( MakeCharm( 1, first, -3, second, 2 ) );
		// More than two abilities: CharmIsIllegal treats it as a one-skill charm.
		Charm^ three = MakeCharm( 0, first, 1, second, 1 );
		three->abilities.Add( gcnew AbilityPair( Ability::static_abilities[ 2 ], 1 ) );
		cases->Add( three );
		return cases;
	}

	// CharmExists and CharmIsIllegal (CharmDatabase.cpp:1001-1004, 1101-1164).
	void WriteCharmValidity( JsonWriter^ json )
	{
		json->Key( L"charm_validity" );
		json->BeginArray();
		for each( Charm^ charm in ValidityCases() )
		{
			json->BeginObject();
			json->Field( L"num_slots", charm->num_slots );
			json->Key( L"abilities" );
			Fixtures::WriteAbilityPairs( json, charm->abilities );
			json->Field( L"hash", charm->GetHash() );
			json->Field( L"exists", CharmExists( charm ) );
			json->Field( L"illegal", CharmIsIllegal( charm ) );
			json->EndObject();
		}
		json->EndArray();
	}

	// CharmDatabase::SaveCustom (CharmDatabase.cpp:90-106), into a string
	// instead of Data/mycharms.txt.
	String^ SaveCustomText( List< Charm^ >^ mycharms )
	{
		IO::StringWriter^ fout = gcnew IO::StringWriter;
		fout->WriteLine( L"#Format: NumSlots,Skill1,Points1,Skill2,Points2" );
		for each( Charm^ ch in mycharms )
		{
			fout->Write( Convert::ToString( ch->num_slots ) );
			for( int i = 0; i < 2; ++i )
			{
				if( i < ch->abilities.Count )
					fout->Write( L"," + ch->abilities[ i ]->ability->name + L"," + Convert::ToString( ch->abilities[ i ]->amount ) );
				else fout->Write( L",," );
			}
			fout->WriteLine();
		}
		return fout->ToString();
	}

	void WriteLineOutcome( JsonWriter^ json, String^ line, String^ outcome )
	{
		json->BeginObject();
		json->Field( L"line", line );
		json->Field( L"outcome", outcome );
		json->EndObject();
	}

	// CharmDatabase::LoadCustom (CharmDatabase.cpp:108-168), reading path
	// instead of Data/mycharms.txt. Each MessageBox becomes the line's
	// outcome. The original lets the slot conversion, and CharmIsIllegal on
	// 4+ slots, throw out of LoadCustom; that ends the file here and is
	// recorded as "exception".
	void WriteLoadCustom( JsonWriter^ json, String^ path )
	{
		List< Charm^ >^ mycharms = gcnew List< Charm^ >;
		bool cheats = false;
		String^ exception_type = nullptr;
		String^ exception_line = nullptr;

		json->BeginObject();
		json->Field( L"file", IO::Path::GetFileName( path ) );
		json->Key( L"lines" );
		json->BeginArray();
		IO::StreamReader^ fin = gcnew IO::StreamReader( path );
		String^ temp;
		try
		{
			while( !fin->EndOfStream )
			{
				temp = fin->ReadLine();
				if( temp == L"" || temp[ 0 ] == L'#' ) continue;
				List< String^ > split;
				Utility::SplitString( %split, temp, L',' );
				if( split.Count != 5 )
				{
					WriteLineOutcome( json, temp, L"wrong_field_count" );
					continue;
				}
				Charm^ charm = gcnew Charm();
				charm->num_slots = Convert::ToUInt32( split[ 0 ] );

				try
				{
					if( split[ 1 ] != L"" )
					{
						Ability^ ab = Ability::FindAbility( split[ 1 ] );
						if( !ab )
						{
							WriteLineOutcome( json, temp, L"no_such_skill" );
							continue;
						}
						charm->abilities.Add( gcnew AbilityPair( ab, Convert::ToInt32( split[ 2 ] ) ) );
					}
					if( split[ 3 ] != L"" )
					{
						Ability^ ab = Ability::FindAbility( split[ 3 ] );
						if( !ab )
						{
							WriteLineOutcome( json, temp, L"no_such_skill" );
							continue;
						}
						charm->abilities.Add( gcnew AbilityPair( ab, Convert::ToInt32( split[ 4 ] ) ) );
					}
				}
				// As broad as the original's catch; only Convert::ToInt32 can throw here.
				catch( Exception^ )
				{
					WriteLineOutcome( json, temp, L"bad_points" );
					continue;
				}

				if( CharmExists( charm ) ||
					!CharmIsIllegal( charm ) )
				{
					charm->custom = true;
					mycharms->Add( charm );
					WriteLineOutcome( json, temp, L"accepted" );
				}
				else
				{
					cheats = true;
					WriteLineOutcome( json, temp, L"rejected" );
				}
			}
		}
		catch( Exception^ error )
		{
			exception_type = error->GetType()->Name;
			exception_line = temp;
		}
		finally
		{
			fin->Close();
		}
		json->EndArray();

		json->Key( L"exception" );
		if( exception_type )
		{
			json->BeginObject();
			json->Field( L"type", exception_type );
			json->Field( L"line", exception_line );
			json->EndObject();
		}
		else
			json->Null();
		json->Field( L"cheater_message", cheats );
		json->Key( L"charms" );
		json->BeginArray();
		for each( Charm^ charm in mycharms )
		{
			json->BeginObject();
			Fixtures::WriteCharmFields( json, charm );
			json->EndObject();
		}
		json->EndArray();
		json->Field( L"saved", SaveCustomText( mycharms ) );
		json->EndObject();
	}

	// Form1::AddCharmToOptimalList (Form1.h:1237-1249).
	void AddCharmToOptimalList( List< Charm^ >^ lst, Charm^ new_charm )
	{
		for( int i = 0; i < lst->Count; ++i )
		{
			Charm^ curr_charm = lst[ i ];
			if( new_charm->StrictlyBetterThan( curr_charm ) )
				lst->RemoveAt( i-- );
			else if( curr_charm->StrictlyBetterThan( new_charm ) ||
					 curr_charm->BasicallyTheSameAs( new_charm ) )
				return;
		}
		lst->Add( new_charm );
	}

	// Charms built from the first three abilities: their two-skill charms,
	// one-skill and slot-only charms, a negative second skill and a copy that
	// differs only in amount (equal under quirk 1).
	List< Charm^ >^ ComparisonCharms()
	{
		List< Charm^ >^ charms = gcnew List< Charm^ >;
		array< Ability^ >^ abilities = { Ability::static_abilities[ 0 ], Ability::static_abilities[ 1 ], Ability::static_abilities[ 2 ] };
		for( int i = 1; i < abilities->Length; ++i )
			for( int j = 0; j < i; ++j )
				for each( Charm^ charm in CharmDatabase::table2[ abilities[ i ] ][ abilities[ j ] ] )
					charms->Add( gcnew Charm( charm ) );
		for each( Ability^ ability in abilities )
		{
			charms->Add( MakeCharm( 0, ability, 3, nullptr, 0 ) );
			charms->Add( MakeCharm( 2, ability, 6, nullptr, 0 ) );
		}
		for( unsigned slots = 0; slots < 4; ++slots )
			charms->Add( MakeCharm( slots, nullptr, 0, nullptr, 0 ) );
		charms->Add( MakeCharm( 1, abilities[ 0 ], 4, abilities[ 1 ], -2 ) );
		charms->Add( MakeCharm( 1, abilities[ 0 ], 5, abilities[ 1 ], -2 ) );
		return charms;
	}

	int IndexOfReference( List< Charm^ >^ charms, Charm^ charm )
	{
		for( int i = 0; i < charms->Count; ++i )
			if( Object::ReferenceEquals( charms[ i ], charm ) )
				return i;
		return -1;
	}

	void WriteOptimalList( JsonWriter^ json, String^ key, List< Charm^ >^ charms, List< Charm^ >^ order )
	{
		List< Charm^ >^ optimal = gcnew List< Charm^ >;
		for each( Charm^ charm in order )
			AddCharmToOptimalList( optimal, charm );
		json->Key( key );
		json->BeginArray();
		for each( Charm^ charm in optimal )
			json->Value( IndexOfReference( charms, charm ) );
		json->EndArray();
	}

	void WriteCharmComparisons( JsonWriter^ json )
	{
		List< Charm^ >^ charms = ComparisonCharms();
		json->Key( L"charm_comparisons" );
		json->BeginObject();
		json->Key( L"charms" );
		json->BeginArray();
		for each( Charm^ charm in charms )
		{
			json->BeginObject();
			Fixtures::WriteCharmFields( json, charm );
			json->EndObject();
		}
		json->EndArray();

		// Charm::operator== (Armor.cpp:300-305) doesn't read the relevant flags.
		json->Key( L"equal" );
		json->BeginArray();
		for each( Charm^ charm in charms )
		{
			Text::StringBuilder^ row = gcnew Text::StringBuilder;
			for each( Charm^ other in charms )
				row->Append( charm == other ? L'1' : L'0' );
			json->Value( row->ToString() );
		}
		json->EndArray();

		array< bool >^ saved_flags = gcnew array< bool >( Ability::static_abilities.Count );
		for( int i = 0; i < saved_flags->Length; ++i )
			saved_flags[ i ] = Ability::static_abilities[ i ]->relevant;

		array< array< int >^ >^ relevant_sets = { gcnew array< int >{}, gcnew array< int >{ 0 }, gcnew array< int >{ 2 },
												  gcnew array< int >{ 0, 1 }, gcnew array< int >{ 0, 1, 2 } };
		List< Charm^ >^ reversed = gcnew List< Charm^ >( charms );
		reversed->Reverse();

		json->Key( L"relevant_sets" );
		json->BeginArray();
		for each( array< int >^ relevant in relevant_sets )
		{
			for each( Ability^ ability in Ability::static_abilities )
				ability->relevant = false;
			for each( int index in relevant )
				Ability::static_abilities[ index ]->relevant = true;

			json->BeginObject();
			json->Key( L"relevant" );
			json->BeginArray();
			for each( int index in relevant )
				json->Value( index );
			json->EndArray();

			// Charm::StrictlyBetterThan and BasicallyTheSameAs (Armor.cpp:241-288, 307-319).
			json->Key( L"strictly_better_than" );
			json->BeginArray();
			for each( Charm^ charm in charms )
			{
				Text::StringBuilder^ row = gcnew Text::StringBuilder;
				for each( Charm^ other in charms )
					row->Append( charm->StrictlyBetterThan( other ) ? L'1' : L'0' );
				json->Value( row->ToString() );
			}
			json->EndArray();
			json->Key( L"basically_the_same_as" );
			json->BeginArray();
			for each( Charm^ charm in charms )
			{
				Text::StringBuilder^ row = gcnew Text::StringBuilder;
				for each( Charm^ other in charms )
					row->Append( charm->BasicallyTheSameAs( other ) ? L'1' : L'0' );
				json->Value( row->ToString() );
			}
			json->EndArray();
			WriteOptimalList( json, L"optimal_forward", charms, charms );
			WriteOptimalList( json, L"optimal_reverse", charms, reversed );
			json->EndObject();
		}
		json->EndArray();
		json->EndObject();

		for( int i = 0; i < saved_flags->Length; ++i )
			Ability::static_abilities[ i ]->relevant = saved_flags[ i ];
	}
}

void ModelDump::Write( List< String^ >^ mycharms_paths, String^ out_path )
{
	JsonWriter^ json = gcnew JsonWriter;
	json->BeginObject();
	WriteSkillThresholds( json );
	WriteDecorationComparisons( json );
	WriteCharmValidity( json );
	json->Key( L"load_custom" );
	json->BeginArray();
	for each( String^ path in mycharms_paths )
		WriteLoadCustom( json, path );
	json->EndArray();
	WriteCharmComparisons( json );
	json->EndObject();
	json->WriteToFile( out_path );
}
