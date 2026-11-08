#pragma once

// L1 fixtures for Solution.cpp internals that don't depend on a query.
namespace SolutionProbe
{
	// Writes what GetScore's point_score lookup (Solution.cpp:324-329) returns
	// for actual_good 0-22. point_score has 6 elements; MatchesQuery reaches
	// indices up to 20 on shipped data. In this build the words after the
	// array are CLR method thunks, patched in at load time, so their values
	// change from run to run. GetScore's result is only ever compared
	// (Solution.cpp:338), so the fixture records the comparisons instead: the
	// in-bounds values, that every out-of-bounds value is above all of them,
	// and their order (with the gaps between them). Also lists the private
	// Solution methods the trace fixtures call through reflection, so a
	// missing one fails here first.
	void Write( System::String^ out_path );

	// point_score[ 0 .. count - 1 ] as GetScore returns it.
	array< int >^ PointScores( const unsigned count );
}
