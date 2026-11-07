#include "stdafx.h"
#include "QueryFile.h"
#include "Armor.h"
#include "LoadedData.h"
#include "Skill.h"
#include "Solution.h"

using namespace System;
using namespace System::Collections::Generic;

namespace
{
	// One configuration for both directions, so any query that reads can be echoed.
	Web::Script::Serialization::JavaScriptSerializer^ MakeSerializer()
	{
		Web::Script::Serialization::JavaScriptSerializer^ serializer = gcnew Web::Script::Serialization::JavaScriptSerializer;
		serializer->MaxJsonLength = Int32::MaxValue;
		return serializer;
	}

	// The GUI's NumericUpDown ranges (Form1.h:655-656, :681, :708-709).
	unsigned GetRanged( QueryFile::JsonObject^ spec, String^ key, const int minimum, const int maximum )
	{
		const int value = QueryFile::GetInt( spec, key );
		if( value < minimum || value > maximum )
			throw gcnew FormatException( key + L" must be " + minimum + L"-" + maximum + L" as in the GUI, got " + value );
		return unsigned( value );
	}
}

QueryFile::JsonObject^ QueryFile::Read( String^ path )
{
	return safe_cast< JsonObject^ >( MakeSerializer()->DeserializeObject( IO::File::ReadAllText( path ) ) );
}

String^ QueryFile::Serialize( JsonObject^ spec )
{
	return MakeSerializer()->Serialize( spec );
}

String^ QueryFile::Language( String^ path )
{
	return GetString( Read( path ), L"language" );
}

int QueryFile::GetInt( JsonObject^ spec, String^ key ) { return Convert::ToInt32( spec[ key ] ); }
bool QueryFile::GetBool( JsonObject^ spec, String^ key ) { return Convert::ToBoolean( spec[ key ] ); }
String^ QueryFile::GetString( JsonObject^ spec, String^ key ) { return safe_cast< String^ >( spec[ key ] ); }
array< Object^ >^ QueryFile::GetArray( JsonObject^ spec, String^ key ) { return safe_cast< array< Object^ >^ >( spec[ key ] ); }

// Skills are indices into Skill::static_skills, as the GUI saves them.
Query^ QueryFile::FormulateQuery( LoadedData^ data, JsonObject^ spec )
{
	Query^ query = gcnew Query;
	for( int i = 0; i < int( Armor::ArmorType::NumArmorTypes ); ++i )
	{
		query->rel_armor.Add( gcnew List_t< Armor^ >() );
		query->inf_armor.Add( gcnew List_t< Armor^ >() );
	}
	query->weapon_slots_allowed = GetRanged( spec, L"weapon_slots", 0, 3 );
	query->elder_star = GetRanged( spec, L"elder_star", 1, 6 );
	query->hr = GetRanged( spec, L"hr", 1, 6 );

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
