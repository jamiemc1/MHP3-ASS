#include "stdafx.h"
#include "RelevanceDump.h"
#include "Fixtures.h"
#include "Json.h"
#include "QueryFile.h"
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
	void WriteArmorList( JsonWriter^ json, String^ key, List_t< Armor^ >^ armors )
	{
		json->Key( key );
		json->BeginArray();
		for each( Armor^ armor in armors )
		{
			json->BeginObject();
			json->Field( L"index", armor->index );
			json->Field( L"no_skills", armor->no_skills );
			json->Key( L"danger" );
			Fixtures::WriteAbilityRef( json, armor->danger );
			json->EndObject();
		}
		json->EndArray();
	}

	void WriteDecorationList( JsonWriter^ json, String^ key, List_t< Decoration^ >% decorations )
	{
		json->Key( key );
		json->BeginArray();
		for each( Decoration^ decoration in decorations )
			json->Value( decoration->index );
		json->EndArray();
	}

	// CharmDatabase::GetCharms( query, use_two_skill_charms ), CharmDatabase.cpp:41-86.
	// Records the exception type instead if it throws.
	void WriteCharms( JsonWriter^ json, String^ key, Query^ query, const bool use_two_skill_charms )
	{
		List_t< Charm^ >^ charms = nullptr;
		String^ exception_type = nullptr;
		try
		{
			charms = CharmDatabase::GetCharms( query, use_two_skill_charms );
		}
		catch( Exception^ error )
		{
			exception_type = error->GetType()->Name;
		}
		json->Key( key );
		json->BeginObject();
		json->Field( L"exception", exception_type );
		json->Key( L"charms" );
		json->BeginArray();
		if( charms )
		{
			for each( Charm^ charm in charms )
			{
				json->BeginObject();
				Fixtures::WriteCharmFields( json, charm );
				json->EndObject();
			}
		}
		json->EndArray();
		json->EndObject();
	}
}

void RelevanceDump::Run( String^ query_path, String^ out_path )
{
	QueryFile::JsonObject^ spec = QueryFile::Read( query_path );
	LoadedData^ data = gcnew LoadedData;
	Query^ query = QueryFile::FormulateQuery( data, spec );

	JsonWriter^ json = gcnew JsonWriter;
	json->BeginObject();
	json->Field( L"id", QueryFile::GetString( spec, L"id" ) );
	// The query exactly as the harness parsed it, so tests can tell when the
	// query file has changed since this golden was generated.
	json->Field( L"query_json", QueryFile::Serialize( spec ) );

	json->Key( L"rel_abilities" );
	json->BeginArray();
	for each( Ability^ ability in query->rel_abilities )
		json->Value( ability->static_index );
	json->EndArray();

	json->Key( L"relevant_flags" );
	json->BeginArray();
	for each( Ability^ ability in Ability::static_abilities )
	{
		if( ability->relevant )
			json->Value( ability->static_index );
	}
	json->EndArray();

	array< String^ >^ slot_names = Fixtures::ArmorSlotNames();
	json->Key( L"armor" );
	json->BeginObject();
	for( int i = 0; i < query->rel_armor.Count; ++i )
	{
		json->Key( slot_names[ i ] );
		json->BeginObject();
		WriteArmorList( json, L"relevant", query->rel_armor[ i ] );
		WriteArmorList( json, L"inferior", query->inf_armor[ i ] );
		json->EndObject();
	}
	json->EndObject();

	json->Key( L"decorations" );
	json->BeginObject();
	WriteDecorationList( json, L"relevant", query->rel_decorations );
	WriteDecorationList( json, L"inferior", query->inf_decorations );
	json->EndObject();

	WriteCharms( json, L"charms_one_skill", query, false );
	WriteCharms( json, L"charms_two_skill", query, true );

	json->EndObject();
	json->WriteToFile( out_path );
}

void RelevanceDump::WriteBestDecorations( String^ out_path )
{
	const unsigned min_rank = 1, max_rank = 6, max_slots = 3;

	JsonWriter^ json = gcnew JsonWriter;
	json->BeginObject();
	json->Field( L"min_rank", min_rank );
	json->Field( L"max_rank", max_rank );
	json->Field( L"max_slots", max_slots );
	// best[hr - min_rank][elder_star - min_rank][slots]: a decoration index,
	// -1 for none, or -2 where the call threw (the ability's "exception").
	json->Key( L"abilities" );
	json->BeginArray();
	for each( Ability^ ability in Ability::static_abilities )
	{
		String^ exception_type = nullptr;
		json->BeginObject();
		json->Field( L"ability", ability->static_index );
		json->Key( L"best" );
		json->BeginArray();
		for( unsigned hr = min_rank; hr <= max_rank; ++hr )
		{
			json->BeginArray();
			for( unsigned elder_star = min_rank; elder_star <= max_rank; ++elder_star )
			{
				Query^ query = gcnew Query;
				query->hr = hr;
				query->elder_star = elder_star;
				json->BeginArray();
				for( unsigned slots = 0; slots <= max_slots; ++slots )
				{
					try
					{
						Decoration^ best = Decoration::GetBestDecoration( ability, slots, query );
						// index is unsigned: convert before mixing it with -1.
						json->Value( best ? int( best->index ) : -1 );
					}
					catch( Exception^ error )
					{
						String^ type = error->GetType()->Name;
						if( exception_type && exception_type != type )
							throw gcnew InvalidOperationException( L"GetBestDecoration threw both " + exception_type + L" and " + type );
						exception_type = type;
						json->Value( -2 );
					}
				}
				json->EndArray();
			}
			json->EndArray();
		}
		json->EndArray();
		json->Field( L"exception", exception_type );
		json->EndObject();
	}
	json->EndArray();
	json->EndObject();
	json->WriteToFile( out_path );
}
