#include "stdafx.h"
#include "SolutionProbe.h"
#include "Json.h"
#include "LegacySolution.h"

using namespace System;
using namespace System::Collections::Generic;

array< int >^ SolutionProbe::PointScores( const unsigned count )
{
	// GetScore only reads data for a decoration with a second ability
	// (Solution.cpp:327), so a one-ability decoration lets it run without one.
	Decoration^ decoration = gcnew Decoration;
	decoration->abilities.Add( gcnew AbilityPair( Ability::static_abilities[ 0 ], 1 ) );

	array< int >^ scores = gcnew array< int >( count );
	for( unsigned actual_good = 0; actual_good < count; ++actual_good )
		scores[ actual_good ] = GetScore( decoration, nullptr, actual_good ).first;
	return scores;
}

void SolutionProbe::Write( String^ out_path )
{
	const unsigned in_bounds = 6, count = 23;
	array< int >^ scores = PointScores( count );

	// Dense rank of each score among all of them: equal scores share a rank,
	// and a higher score has a higher rank. This is all GetBestDecoration's
	// comparison can see.
	SortedSet< int >^ distinct = gcnew SortedSet< int >( scores );
	List< int >^ ordered = gcnew List< int >( distinct );

	JsonWriter^ json = gcnew JsonWriter;
	json->BeginObject();
	json->Key( L"point_score_in_bounds" );
	json->BeginArray();
	for( unsigned i = 0; i < in_bounds; ++i )
		json->Value( scores[ i ] );
	json->EndArray();
	json->Key( L"point_score_rank" );
	json->BeginArray();
	for each( int score in scores )
		json->Value( ordered->IndexOf( score ) );
	json->EndArray();

	array< String^ >^ methods = {
		L"FixBadSkills", L"CheckBadSkills", L"ReorderGems", L"CalculateExtraSkills",
		L"ReduceSlots", L"ReduceSkills", L"RearrangeDecorations", L"ReduceCharm" };
	json->Key( L"private_methods" );
	json->BeginArray();
	for each( String^ method in methods )
	{
		if( !Solution::typeid->GetMethod( method, LegacySolution::PrivateInstance() ) )
			throw gcnew MissingMethodException( L"Solution", method );
		json->Value( method );
	}
	json->EndArray();
	json->EndObject();
	json->WriteToFile( out_path );
}
