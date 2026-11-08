#include "stdafx.h"
#include "SaveDump.h"
#include "Fixtures.h"
#include "Armor.h"
#include "CharmDatabase.h"
#include "PSPCryptoEngine.h"
#include "SaveDataEncryption.h"
#include "Skill.h"

using namespace System;
using namespace System::Collections::Generic;

namespace
{
	ref struct ImportedCharm
	{
		Charm^ charm;
		array< Byte >^ raw;
	};

	// ImportCharms::LoadCharms( data, char_num ), ImportCharms.h:369-436.
	List< ImportedCharm^ >^ LoadCharacterCharms( array< Byte >^ data, const unsigned char_num, String^% name )
	{
		const unsigned index = 0x800 + char_num * 0x60000;
		name = nullptr;
		if( !data[ index ] )
			return nullptr;

		List< ImportedCharm^ >^ charms = gcnew List< ImportedCharm^ >;
		unsigned name_end = index;
		while( data[ name_end ] )
			name_end++;

		for( unsigned i = 0; i < 1000; ++i )
		{
			const unsigned equipment_index = index + 0x168 + i * 12;
			array< Byte >^ charm_data = gcnew array< Byte >( 6 );
			array< Byte >::Copy( data, equipment_index, charm_data, 0, charm_data->Length );
			if( charm_data[ 0 ] == 1 && charm_data[ 1 ] == 0x65 )
			{
				const int amount1 = ( ( charm_data[ 2 ] >> 4 ) + 2 ) % 16;
				const int amount2 = ( ( charm_data[ 3 ] & 0x3c ) >> 2 ) - !( charm_data[ 3 ] & 0x80 ) * 16 + 2;
				const int ability1 = ( charm_data[ 4 ] & 0x7f );
				const int ability2 = !!( charm_data[ 4 ] & 0x80 ) + ( ( charm_data[ 5 ] & 0x3f ) << 1 );
				const int num_slots = charm_data[ 5 ] >> 6;
				Charm^ charm = gcnew Charm( num_slots );
				if( ability1 )
					charm->abilities.Add( gcnew AbilityPair( Ability::ordered_abilities[ ability1 - 1 ], amount1 ) );
				if( ability2 )
					charm->abilities.Add( gcnew AbilityPair( Ability::ordered_abilities[ ability2 - 1 ], amount2 ) );
				if( !CharmExists( charm ) && CharmIsIllegal( charm ) )
					charm->hacked = true;

				ImportedCharm^ imported = gcnew ImportedCharm;
				imported->charm = charm;
				imported->raw = charm_data;
				charms->Add( imported );
			}
		}
		if( charms->Count > 0 )
		{
			Text::Encoding^ encoding = Text::Encoding::GetEncoding( L"utf-16LE" );
			name = encoding->GetString( data, index, name_end - index );
		}
		return charms;
	}

	// ImportCharms::SelectDefault( c ), ImportCharms.h:337-367, with the list view's
	// check boxes as a bool array. Marks every ability relevant, as the dialog does.
	array< bool >^ SelectBest( List< ImportedCharm^ >^ imported )
	{
		List_t< Charm^ >^ current_charms = gcnew List_t< Charm^ >;
		for each( ImportedCharm^ item in imported )
			current_charms->Add( item->charm );

		array< bool >^ is_checked = gcnew array< bool >( current_charms->Count );
		for each( Ability^ a in Ability::static_abilities )
		{
			a->relevant = true;
		}
		for( int i = 0; i < current_charms->Count; ++i )
		{
			if( current_charms[ i ]->hacked )
				continue;
			else
				is_checked[ i ] = true;
			for( int j = 0; j < i; j++ )
			{
				if( is_checked[ j ] )
				{
					if( current_charms[ i ]->StrictlyBetterThan( current_charms[ j ] ) )
						is_checked[ j ] = false;
					else if( current_charms[ j ]->StrictlyBetterThan( current_charms[ i ] ) ||
						current_charms[ i ] == current_charms[ j ] )
						is_checked[ i ] = false;
				}
			}
		}
		return is_checked;
	}

	// One line of CharmDatabase::SaveCustom(), CharmDatabase.cpp:95-105.
	String^ MyCharmsLine( Charm^ ch )
	{
		Text::StringBuilder^ line = gcnew Text::StringBuilder;
		line->Append( Convert::ToString( ch->num_slots ) );
		for( int i = 0; i < 2; ++i )
		{
			if( i < ch->abilities.Count )
				line->Append( L"," + ch->abilities[ i ]->ability->name + L"," + Convert::ToString( ch->abilities[ i ]->amount ) );
			else
				line->Append( L",," );
		}
		return line->ToString();
	}

	void WriteCharm( JsonWriter^ json, ImportedCharm^ imported, const bool selected )
	{
		Charm^ charm = imported->charm;
		json->BeginObject();
		json->Field( L"raw", Fixtures::HexLower( imported->raw ) );
		Fixtures::WriteCharmFields( json, charm );
		json->Field( L"hacked", charm->hacked );
		json->Field( L"select_best", selected );
		json->EndObject();
	}
}

void SaveDump::Write( String^ save_path, String^ out_path )
{
	array< Byte >^ raw = IO::File::ReadAllBytes( save_path );
	if( raw->Length != 0x121010 )
		throw gcnew InvalidOperationException( L"Not an MHP3rd save file: expected 0x121010 bytes, got " + raw->Length );

	String^ raw_sha256 = Fixtures::Sha256Hex( raw );
	PSPCryptoEngine engine;
	array< Byte >^ data = engine.DecryptSaveData( safe_cast< array< Byte >^ >( raw->Clone() ) );
	String^ system_layer_sha256 = Fixtures::Sha256Hex( data );
	DecryptSaveData( data );
	String^ game_layer_sha256 = Fixtures::Sha256Hex( data );

	JsonWriter^ json = gcnew JsonWriter;
	json->BeginObject();
	json->Field( L"input_length", raw->Length );
	json->Field( L"input_sha256", raw_sha256 );
	json->Field( L"system_layer_length", data->Length );
	json->Field( L"system_layer_sha256", system_layer_sha256 );
	json->Field( L"game_layer_sha256", game_layer_sha256 );

	// The dialog opens on the first character that has charms (ImportCharms.h:448-455);
	// Import adds that character's checked, non-hacked charms (AddCharms, :278-292).
	List< String^ >^ mycharms_lines = gcnew List< String^ >;
	bool default_character_found = false;
	json->Key( L"characters" );
	json->BeginArray();
	for( unsigned char_num = 0; char_num < 3; ++char_num )
	{
		String^ name;
		List< ImportedCharm^ >^ imported = LoadCharacterCharms( data, char_num, name );
		const bool is_default_character = !default_character_found && imported != nullptr && imported->Count > 0;
		default_character_found = default_character_found || is_default_character;

		json->BeginObject();
		json->Field( L"slot", char_num );
		json->Field( L"present", imported != nullptr );
		json->Field( L"name", name );
		json->Field( L"default_selection", is_default_character );
		json->Key( L"charms" );
		json->BeginArray();
		if( imported != nullptr )
		{
			array< bool >^ selected = SelectBest( imported );
			for( int i = 0; i < imported->Count; ++i )
			{
				WriteCharm( json, imported[ i ], selected[ i ] );
				if( is_default_character && selected[ i ] && !imported[ i ]->charm->hacked )
					mycharms_lines->Add( MyCharmsLine( imported[ i ]->charm ) );
			}
		}
		json->EndArray();
		json->EndObject();
	}
	json->EndArray();

	// What Import writes with the default selection. Existing charms are always
	// replaced: btnOK_Click tests the check box handle, not its state
	// (ImportCharms.h:298; docs/quirks.md).
	json->Key( L"mycharms_txt" );
	json->BeginArray();
	json->Value( L"#Format: NumSlots,Skill1,Points1,Skill2,Points2" );
	for each( String^ line in mycharms_lines )
		json->Value( line );
	json->EndArray();

	json->EndObject();
	json->WriteToFile( out_path );
}
