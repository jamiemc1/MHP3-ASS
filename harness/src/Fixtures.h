#pragma once
#include "Json.h"
#include "Armor.h"
#include "Skill.h"

// Serialisation shared by every fixture, so a record type always has one
// shape whichever command wrote it.
namespace Fixtures
{
	inline array< System::String^ >^ ArmorSlotNames()
	{
		array< System::String^ >^ names = { L"head", L"body", L"arms", L"waist", L"legs" };
		return names;
	}

	inline System::String^ HexLower( array< System::Byte >^ bytes )
	{
		return System::BitConverter::ToString( bytes )->Replace( L"-", L"" )->ToLowerInvariant();
	}

	inline System::String^ Sha256Hex( array< System::Byte >^ data )
	{
		System::Security::Cryptography::SHA256^ sha = System::Security::Cryptography::SHA256::Create();
		try
		{
			return HexLower( sha->ComputeHash( data ) );
		}
		finally
		{
			delete sha;
		}
	}

	inline void WriteAbilityRef( JsonWriter^ json, Ability^ ability )
	{
		if( !ability )
			json->Null();
		else
			json->Value( ability->static_index );
	}

	inline void WriteAbilityPairs( JsonWriter^ json, System::Collections::Generic::List< AbilityPair^ >% pairs )
	{
		json->BeginArray();
		for each( AbilityPair^ pair in pairs )
		{
			json->BeginObject();
			json->Key( L"ability" );
			WriteAbilityRef( json, pair->ability );
			json->Field( L"amount", pair->amount );
			json->EndObject();
		}
		json->EndArray();
	}

	// Writes a charm's fields into the object the caller has opened.
	inline void WriteCharmFields( JsonWriter^ json, Charm^ charm )
	{
		json->Field( L"name", charm->GetName() );
		json->Field( L"num_slots", charm->num_slots );
		json->Key( L"abilities" );
		WriteAbilityPairs( json, charm->abilities );
	}
}
