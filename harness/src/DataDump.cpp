#include "stdafx.h"
#include "DataDump.h"
#include "Fixtures.h"
#include "Armor.h"
#include "CharmDatabase.h"
#include "Decoration.h"
#include "LoadedData.h"
#include "Skill.h"

using namespace System;
using namespace System::Collections::Generic;
using Fixtures::WriteAbilityPairs;
using Fixtures::WriteAbilityRef;

namespace
{
	String^ GenderName( Gender gender )
	{
		switch( gender )
		{
		case Gender::MALE: return L"male";
		case Gender::FEMALE: return L"female";
		case Gender::BOTH_GENDERS: return L"both";
		default: return L"unknown:" + Convert::ToString( (int)gender );
		}
	}

	String^ HunterTypeName( HunterType hunter_type )
	{
		switch( hunter_type )
		{
		case HunterType::BLADEMASTER: return L"blademaster";
		case HunterType::GUNNER: return L"gunner";
		case HunterType::BOTH_TYPES: return L"both";
		default: return L"unknown:" + Convert::ToString( (int)hunter_type );
		}
	}

	void WriteComponents( JsonWriter^ json, List< MaterialComponent^ >% components )
	{
		json->BeginArray();
		for each( MaterialComponent^ component in components )
		{
			json->BeginObject();
			json->Field( L"material", component->material == nullptr ? nullptr : component->material->name );
			json->Field( L"amount", component->amount );
			json->EndObject();
		}
		json->EndArray();
	}

	void WriteCharm( JsonWriter^ json, Charm^ charm )
	{
		json->BeginObject();
		Fixtures::WriteCharmFields( json, charm );
		json->EndObject();
	}

	void WriteAbilities( JsonWriter^ json )
	{
		json->Key( L"abilities" );
		json->BeginArray();
		for each( Ability^ ability in Ability::static_abilities )
		{
			json->BeginObject();
			json->Field( L"static_index", ability->static_index );
			json->Field( L"name", ability->name );
			json->Field( L"order", ability->order );
			json->Field( L"auto_guard", ability->auto_guard );
			json->Field( L"is_torso_inc", ability == Ability::torso_inc );
			json->Key( L"tags" );
			json->BeginArray();
			for each( SkillTag^ tag in ability->tags )
				json->Value( tag->name );
			json->EndArray();
			// Dictionary enumeration order: GetSkill() walks it.
			json->Key( L"skills" );
			json->BeginArray();
			for each( KeyValuePair< int, Skill^ > entry in ability->skills )
			{
				json->BeginObject();
				json->Field( L"points", entry.Key );
				json->Field( L"skill", entry.Value->name );
				json->EndObject();
			}
			json->EndArray();
			json->EndObject();
		}
		json->EndArray();

		json->Key( L"ordered_abilities" );
		json->BeginArray();
		for each( Ability^ ability in Ability::ordered_abilities )
			WriteAbilityRef( json, ability );
		json->EndArray();
	}

	void WriteSkills( JsonWriter^ json )
	{
		json->Key( L"skills" );
		json->BeginArray();
		for( int i = 0; i < Skill::static_skills.Count; ++i )
		{
			Skill^ skill = Skill::static_skills[ i ];
			json->BeginObject();
			json->Field( L"index", i );
			json->Field( L"name", skill->name );
			json->Field( L"points_required", skill->points_required );
			json->Key( L"ability" );
			WriteAbilityRef( json, skill->ability );
			json->EndObject();
		}
		json->EndArray();

		json->Key( L"ordered_skills" );
		json->BeginArray();
		for each( Skill^ skill in Skill::ordered_skills )
			json->Value( Skill::static_skills.IndexOf( skill ) );
		json->EndArray();
	}

	void WriteArmors( JsonWriter^ json )
	{
		array< String^ >^ slot_names = Fixtures::ArmorSlotNames();
		json->Key( L"armors" );
		json->BeginObject();
		for( int type = 0; type < Armor::static_armors->Length; ++type )
		{
			json->Key( slot_names[ type ] );
			json->BeginArray();
			for each( Armor^ armor in Armor::static_armors[ type ] )
			{
				json->BeginObject();
				json->Field( L"index", armor->index );
				json->Field( L"name", armor->name );
				json->Field( L"hr", armor->hr );
				json->Field( L"elder_star", armor->elder_star );
				json->Field( L"num_slots", armor->num_slots );
				json->Field( L"defence", armor->defence );
				json->Field( L"max_defence", armor->max_defence );
				json->Field( L"rarity", armor->rarity );
				json->Field( L"difficulty", armor->difficulty );
				json->Field( L"fire_res", armor->fire_res );
				json->Field( L"water_res", armor->water_res );
				json->Field( L"thunder_res", armor->thunder_res );
				json->Field( L"ice_res", armor->ice_res );
				json->Field( L"dragon_res", armor->dragon_res );
				json->Field( L"gender", GenderName( armor->gender ) );
				json->Field( L"hunter_type", HunterTypeName( armor->type ) );
				json->Field( L"torso_inc", armor->torso_inc );
				json->Field( L"no_skills", armor->no_skills );
				json->Field( L"is_piercing", armor->is_piercing );
				json->Field( L"is_event", armor->is_event );
				json->Key( L"danger" );
				WriteAbilityRef( json, armor->danger );
				json->Key( L"abilities" );
				WriteAbilityPairs( json, armor->abilities );
				json->Key( L"components" );
				WriteComponents( json, armor->components );
				json->EndObject();
			}
			json->EndArray();
		}
		json->EndObject();
	}

	void WriteDecorations( JsonWriter^ json )
	{
		json->Key( L"decorations" );
		json->BeginArray();
		for each( Decoration^ decoration in Decoration::static_decorations )
		{
			json->BeginObject();
			json->Field( L"index", decoration->index );
			json->Field( L"name", decoration->name );
			json->Field( L"hr", decoration->hr );
			json->Field( L"elder_star", decoration->elder_star );
			json->Field( L"slots_required", decoration->slots_required );
			json->Field( L"rarity", decoration->rarity );
			json->Field( L"difficulty", decoration->difficulty );
			json->Field( L"is_event", decoration->is_event );
			json->Key( L"abilities" );
			WriteAbilityPairs( json, decoration->abilities );
			json->Key( L"components" );
			WriteComponents( json, decoration->components );
			json->Key( L"components2" );
			WriteComponents( json, decoration->components2 );
			json->EndObject();
		}
		json->EndArray();

		// Per-ability lists in dictionary enumeration order: GetRelevantDecorations walks them.
		json->Key( L"decorations_by_ability" );
		json->BeginArray();
		for each( KeyValuePair< Ability^, List< Decoration^ >^ > entry in Decoration::static_decoration_ability_map )
		{
			json->BeginObject();
			json->Field( L"ability", entry.Key->static_index );
			json->Key( L"decorations" );
			json->BeginArray();
			for each( Decoration^ decoration in entry.Value )
				json->Value( decoration->index );
			json->EndArray();
			json->EndObject();
		}
		json->EndArray();
	}

	void WriteMaterials( JsonWriter^ json )
	{
		json->Key( L"materials" );
		json->BeginArray();
		for each( Material^ material in Material::static_materials )
		{
			json->BeginObject();
			json->Field( L"name", material->name );
			json->Field( L"event_only", material->event_only );
			json->Field( L"difficulty", material->difficulty );
			json->EndObject();
		}
		json->EndArray();

		json->Key( L"skill_tags" );
		json->BeginArray();
		for each( SkillTag^ tag in SkillTag::tags )
			json->Value( tag->name );
		json->EndArray();
	}

	void WriteCharmTables( JsonWriter^ json )
	{
		json->Key( L"charm_table" );
		json->BeginArray();
		for( int charm_type = 0; charm_type < CharmDatabase::table->GetLength( 0 ); ++charm_type )
		{
			for( int slots = 0; slots < CharmDatabase::table->GetLength( 1 ); ++slots )
			{
				json->BeginObject();
				json->Field( L"charm_type", charm_type );
				json->Field( L"slots", slots );
				json->Key( L"max_points" );
				json->BeginArray();
				for each( KeyValuePair< Ability^, unsigned > entry in CharmDatabase::table[ charm_type, slots ] )
				{
					json->BeginObject();
					json->Field( L"ability", entry.Key->static_index );
					json->Field( L"points", entry.Value );
					json->EndObject();
				}
				json->EndArray();
				json->EndObject();
			}
		}
		json->EndArray();

		// table2 shares one list between [a][b] and [b][a]; write each pair once, a > b.
		json->Key( L"two_skill_charms" );
		json->BeginArray();
		for( int i = 1; i < Ability::static_abilities.Count; ++i )
		{
			for( int j = 0; j < i; ++j )
			{
				List< Charm^ >^ charms = CharmDatabase::table2[ Ability::static_abilities[ i ] ][ Ability::static_abilities[ j ] ];
				if( charms->Count == 0 )
					continue;
				json->BeginObject();
				json->Field( L"ability_a", i );
				json->Field( L"ability_b", j );
				json->Key( L"charms" );
				json->BeginArray();
				for each( Charm^ charm in charms )
					WriteCharm( json, charm );
				json->EndArray();
				json->EndObject();
			}
		}
		json->EndArray();

		// Full lists in insertion order: CharmIsIllegal and FindCharm2 walk them.
		json->Key( L"table_hashes" );
		json->BeginArray();
		for( int table_number = 0; table_number < CharmDatabase::table_hashes->GetLength( 0 ); ++table_number )
		{
			for( int charm_type = 0; charm_type < CharmDatabase::table_hashes->GetLength( 1 ); ++charm_type )
			{
				for( int slots = 0; slots < CharmDatabase::table_hashes->GetLength( 2 ); ++slots )
				{
					List< unsigned >^ hashes = CharmDatabase::table_hashes[ table_number, charm_type, slots ];
					json->BeginObject();
					json->Field( L"table", table_number );
					json->Field( L"charm_type", charm_type );
					json->Field( L"slots", slots );
					json->Key( L"hashes" );
					json->BeginArray();
					for each( unsigned hash in hashes )
						json->Value( hash );
					json->EndArray();
					json->EndObject();
				}
			}
		}
		json->EndArray();

		json->Key( L"charm_hashes" );
		json->BeginArray();
		for each( unsigned hash in CharmDatabase::charm_hashes )
			json->Value( hash );
		json->EndArray();
	}

	void WriteNameList( JsonWriter^ json, String^ key, IEnumerable< String^ >^ names )
	{
		json->Key( key );
		json->BeginArray();
		for each( String^ name in names )
			json->Value( name );
		json->EndArray();
	}
}

void DataDump::WriteGameData( String^ out_path )
{
	JsonWriter^ json = gcnew JsonWriter;
	json->BeginObject();
	WriteAbilities( json );
	WriteSkills( json );
	WriteArmors( json );
	WriteDecorations( json );
	WriteMaterials( json );
	json->EndObject();
	json->WriteToFile( out_path );
}

void DataDump::WriteCharmDatabase( String^ out_path )
{
	JsonWriter^ json = gcnew JsonWriter;
	json->BeginObject();
	WriteCharmTables( json );
	json->EndObject();
	json->WriteToFile( out_path );
}

void DataDump::WriteNames( String^ out_path )
{
	JsonWriter^ json = gcnew JsonWriter;
	json->BeginObject();

	List< String^ >^ ability_names = gcnew List< String^ >;
	for each( Ability^ ability in Ability::static_abilities )
		ability_names->Add( ability->name );
	WriteNameList( json, L"abilities", ability_names );

	List< String^ >^ skill_names = gcnew List< String^ >;
	for each( Skill^ skill in Skill::static_skills )
		skill_names->Add( skill->name );
	WriteNameList( json, L"skills", skill_names );

	array< String^ >^ slot_names = Fixtures::ArmorSlotNames();
	json->Key( L"armors" );
	json->BeginObject();
	for( int type = 0; type < Armor::static_armors->Length; ++type )
	{
		List< String^ >^ armor_names = gcnew List< String^ >;
		for each( Armor^ armor in Armor::static_armors[ type ] )
			armor_names->Add( armor->name );
		WriteNameList( json, slot_names[ type ], armor_names );
	}
	json->EndObject();

	List< String^ >^ decoration_names = gcnew List< String^ >;
	for each( Decoration^ decoration in Decoration::static_decorations )
		decoration_names->Add( decoration->name );
	WriteNameList( json, L"decorations", decoration_names );

	List< String^ >^ material_names = gcnew List< String^ >;
	for each( Material^ material in Material::static_materials )
		material_names->Add( material->name );
	WriteNameList( json, L"materials", material_names );

	List< String^ >^ tag_names = gcnew List< String^ >;
	for each( SkillTag^ tag in SkillTag::tags )
		tag_names->Add( tag->name );
	WriteNameList( json, L"skill_tags", tag_names );

	json->EndObject();
	json->WriteToFile( out_path );
}
