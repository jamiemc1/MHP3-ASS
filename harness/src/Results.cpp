#include "stdafx.h"
#include "Results.h"
#include "Armor.h"
#include "Common.h"
#include "Decoration.h"
#include "Skill.h"
#include "Solution.h"

using namespace System;
using namespace System::Collections::Generic;

List< Solution^ >^ ResultSet::AddSolutions( List< Solution^ >^ solutions )
{
	List< Solution^ >^ added = gcnew List< Solution^ >;
	for each( Solution^ sol in solutions )
	{
		if( sol->charm )
		{
			if( AddSolution( sol->charm->GetName(), sol ) )
				added->Add( sol );
		}
		else
		{
			all_solutions.Add( sol );
			no_charm_solutions.Add( sol );
			added->Add( sol );
		}
	}
	return added;
}

bool ResultSet::AddSolution( String^ charm, Solution^ sol )
{
	if( SolutionExists( charm, sol ) ) return false;
	if( !charm_solution_map.ContainsKey( charm ) )
		charm_solution_map.Add( charm, gcnew List< Solution^ > );
	charm_solution_map[ charm ]->Add( sol );
	all_solutions.Add( sol );
	return true;
}

void ResultSet::ClearForLoad()
{
	charm_solution_map.Clear();
	all_solutions.Clear();
	no_charm_solutions.Clear();
}

__int64 ResultSet::HashArmor( List< Armor^ >% armors )
{
	__int64 res = 0;
	for( int i = 0; i < armors.Count; ++i )
	{
		res += armors[ i ]->index << ( i * 3 );
	}
	return res;
}

bool ResultSet::SolutionExists( String^ charm, Solution^ sol )
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
