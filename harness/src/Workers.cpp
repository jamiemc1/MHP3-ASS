#include "stdafx.h"
#include "Workers.h"
#include "Armor.h"
#include "CharmDatabase.h"
#include "Skill.h"
#include "Solution.h"

using namespace System;
using namespace System::Collections::Generic;

namespace
{
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
}

namespace Workers
{
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

	int CharmSelectIndex( String^ charm_mode )
	{
		array< String^ >^ modes = { L"none", L"my_charms", L"slotted", L"one_skill", L"two_skill" };
		const int index = Array::IndexOf( modes, charm_mode );
		if( index < 0 )
			throw gcnew FormatException( L"charm_mode must be one of none, my_charms, slotted, one_skill, two_skill; got " + charm_mode );
		return index;
	}

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

	void AddEmptySlotPieces( Query^ query )
	{
		for each( List_t< Armor^ >^ slot in query->rel_armor )
		{
			if( slot->Count == 0 )
				slot->Add( nullptr );
		}
	}

	Solution^ NewJob( array< Armor^ >^ armors, Charm^ charm_template )
	{
		Solution^ job = gcnew Solution();
		for each( Armor^ armor in armors )
			job->armors.Add( armor );
		job->charm = charm_template ? gcnew Charm( charm_template ) : nullptr;
		return job;
	}

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
}
