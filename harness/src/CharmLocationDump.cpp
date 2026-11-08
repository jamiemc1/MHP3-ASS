#include "stdafx.h"
#include "CharmLocationDump.h"
#include "Fixtures.h"
#include "Json.h"
#include "Armor.h"
#include "CharmDatabase.h"
#include "Skill.h"

using namespace System;
using namespace System::Collections::Generic;

namespace
{
	ref struct LocationCall
	{
		Ability^ ability1;
		unsigned points1;
		Ability^ ability2;
		int points2;
		unsigned num_slots;

		LocationCall( Ability^ a1, const unsigned p1, Ability^ a2, const int p2, const unsigned slots )
			: ability1( a1 ), points1( p1 ), ability2( a2 ), points2( p2 ), num_slots( slots ) {}
	};

	void WriteLocation( JsonWriter^ json, CharmLocationData^ location )
	{
		// table[ table, type ]: type 0 mystery, 1 shining, 2 timeworn.
		json->Key( L"table" );
		json->BeginArray();
		for( int table = 0; table < location->table->GetLength( 0 ); ++table )
		{
			json->BeginArray();
			for( int type = 0; type < location->table->GetLength( 1 ); ++type )
				json->Value( location->table[ table, type ] );
			json->EndArray();
		}
		json->EndArray();
		json->Key( L"example" );
		if( location->example )
		{
			json->BeginObject();
			Fixtures::WriteCharmFields( json, location->example );
			json->EndObject();
		}
		else
			json->Null();
	}

	// The calls the fixture makes, in order.
	List< LocationCall^ >^ LocationCalls()
	{
		List< LocationCall^ >^ calls = gcnew List< LocationCall^ >;
		const unsigned max_slots = 3, max_points = 15, pair_sample = 10;

		for( unsigned slots = 0; slots <= max_slots; ++slots )
			calls->Add( gcnew LocationCall( nullptr, 0, nullptr, 0, slots ) );

		for each( Ability^ ability in Ability::static_abilities )
			for( unsigned points = 0; points <= max_points; ++points )
				for( unsigned slots = 0; slots <= max_slots; ++slots )
					calls->Add( gcnew LocationCall( ability, points, nullptr, 0, slots ) );

		// Every pair_sample-th distinct (slots, ability 1, ability 2) in
		// table_hashes order, with the points of its first entry.
		const unsigned ability_count = Ability::static_abilities.Count;
		Dictionary< unsigned, bool >^ seen = gcnew Dictionary< unsigned, bool >;
		int distinct = 0;
		for( int table = 0; table < CharmDatabase::table_hashes->GetLength( 0 ); ++table )
		for( int type = 0; type < CharmDatabase::table_hashes->GetLength( 1 ); ++type )
		for( int slots = 0; slots < CharmDatabase::table_hashes->GetLength( 2 ); ++slots )
		{
			for each( const unsigned hashed in CharmDatabase::table_hashes[ table, type, slots ] )
			{
				const unsigned ability1_index = ( hashed >> 11 ) & 0x7F;
				const unsigned ability2_index = ( hashed >> 18 ) & 0x7F;
				const unsigned points1 = ( hashed >> 2 ) & 0xF;
				const int points2 = int( ( hashed >> 6 ) & 0x1F ) - 12;
				if( ability2_index == ability_count )
					continue;
				const unsigned key = ( unsigned( slots ) << 16 ) | ( ability1_index << 8 ) | ability2_index;
				if( seen->ContainsKey( key ) )
					continue;
				seen->Add( key, true );
				if( distinct++ % pair_sample != 0 )
					continue;
				Ability^ a1 = Ability::static_abilities[ ability1_index ];
				Ability^ a2 = Ability::static_abilities[ ability2_index ];
				calls->Add( gcnew LocationCall( a1, points1, a2, points2, slots ) );
				// Swapped: points2 converts to unsigned, as a caller passing it first would.
				calls->Add( gcnew LocationCall( a2, unsigned( points2 ), a1, int( points1 ), slots ) );
				calls->Add( gcnew LocationCall( a1, points1 + 1, a2, points2, slots ) );
				calls->Add( gcnew LocationCall( a1, points1, a2, points2 + 1, slots ) );
				calls->Add( gcnew LocationCall( a1, points1, a2, -points2, slots ) );
				// The shape quirk 7's parser produces for a two-skill name.
				calls->Add( gcnew LocationCall( a1, 0, a2, points2, slots ) );
			}
		}

		// Negative first points wrap: the parser can't produce these, but they
		// pin the unsigned comparison.
		array< int >^ negatives = { -1, -3, -12 };
		for each( int points in negatives )
			calls->Add( gcnew LocationCall( Ability::static_abilities[ 0 ], unsigned( points ), nullptr, 0, 0 ) );
		return calls;
	}

	void WriteAbilityIndex( JsonWriter^ json, Ability^ ability )
	{
		if( ability )
			json->Value( ability->static_index );
		else
			json->Null();
	}

	Charm^ MakeCharm( const unsigned slots, Ability^ a1, const int p1, Ability^ a2, const int p2 )
	{
		Charm^ charm = gcnew Charm( slots );
		if( a1 )
			charm->abilities.Add( gcnew AbilityPair( a1, p1 ) );
		if( a2 )
			charm->abilities.Add( gcnew AbilityPair( a2, p2 ) );
		return charm;
	}

	// Utility::UpdateContextMenu( strip, name ) with an empty cache.
	void WriteParse( JsonWriter^ json, String^ language, String^ name )
	{
		CharmDatabase::charm_location_cache.Clear();
		System::Windows::Forms::ContextMenuStrip^ strip = gcnew System::Windows::Forms::ContextMenuStrip;
		String^ exception_type = nullptr;
		try
		{
			Utility::UpdateContextMenu( strip, name );
		}
		catch( Exception^ error )
		{
			exception_type = error->GetType()->Name;
		}
		json->BeginObject();
		json->Field( L"language", language );
		json->Field( L"name", name );
		json->Field( L"exception", exception_type );
		if( !exception_type )
		{
			WriteLocation( json, CharmDatabase::charm_location_cache[ name ] );
			json->Field( L"header", strip->Items[ 0 ]->Text );
		}
		json->EndObject();
		delete strip;
	}
}

void CharmLocationDump::Write( String^ out_path )
{
	String^ default_language = L"English (TeamHGG)";
	const int names_per_other_language = 200;

	JsonWriter^ json = gcnew JsonWriter;
	json->BeginObject();

	// Names for the parser: each call with a match, as GetName() writes it.
	List< Charm^ >^ named = gcnew List< Charm^ >;

	json->Key( L"find_charm2" );
	json->BeginArray();
	for each( LocationCall^ call in LocationCalls() )
	{
		CharmLocationData^ location = FindCharm2( call->ability1, call->points1, call->ability2, call->points2, call->num_slots );
		json->BeginObject();
		json->Key( L"ability1" );
		WriteAbilityIndex( json, call->ability1 );
		json->Field( L"points1", call->points1 );
		json->Key( L"ability2" );
		WriteAbilityIndex( json, call->ability2 );
		json->Field( L"points2", call->points2 );
		json->Field( L"num_slots", call->num_slots );
		WriteLocation( json, location );
		json->EndObject();

		bool any = false;
		for each( unsigned count in location->table )
			any = any || count > 0;
		// Names exist for first points 1-15 only (a wrapped negative has none).
		if( call->ability1 && ( any || call->ability2 ) && call->points1 >= 1 && call->points1 <= 15 )
			named->Add( MakeCharm( call->num_slots, call->ability1, int( call->points1 ), call->ability2, call->points2 ) );
	}
	json->EndArray();

	Ability^ attack = Ability::FindAbility( L"Attack" );
	Ability^ sharpness = Ability::FindAbility( L"Sharpness" );
	if( !attack || !sharpness )
		throw gcnew InvalidOperationException( L"The hand-written charms need Attack and Sharpness" );
	// A negative second skill, a zero second skill and a negative first skill.
	named->Add( MakeCharm( 0, attack, 4, sharpness, -3 ) );
	named->Add( MakeCharm( 1, attack, 4, sharpness, 0 ) );
	named->Add( MakeCharm( 0, attack, -3, nullptr, 0 ) );
	array< String^ >^ literal_names = {
		L"OOO", L"OO-", L"O--",
		L"+4 No Such Skill ---", L"+4 No Such Skill, +3 Sharpness O--", L"+4 Attack, +3 No Such Skill O--" };

	json->Key( L"parse_and_find" );
	json->BeginArray();
	for each( Charm^ charm in named )
		WriteParse( json, default_language, charm->GetName() );
	for each( String^ name in literal_names )
		WriteParse( json, default_language, name );

	array< String^ >^ language_dirs = IO::Directory::GetDirectories( L"Data/Languages" );
	Array::Sort( language_dirs, StringComparer::Ordinal );
	const int stride = Math::Max( 1, named->Count / names_per_other_language );
	for each( String^ dir in language_dirs )
	{
		String^ language = IO::Path::GetFileName( dir );
		if( String::Equals( language, default_language ) )
			continue;
		StringTable::LoadLanguage( language );
		for( int i = 0; i < named->Count; i += stride )
			WriteParse( json, language, named[ i ]->GetName() );
	}
	StringTable::LoadLanguage( default_language );
	json->EndArray();

	json->EndObject();
	json->WriteToFile( out_path );
}
