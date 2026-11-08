#pragma once
#include "Solution.h"
#include "Decoration.h"
#include "Skill.h"
#include <cliext/utility>

// Solution.cpp's file-level definitions, for fixtures that run MatchesQuery
// one stage at a time. CalculationData is copied token for token from
// Solution.cpp:9-16, so the linker merges it with the original type; any
// difference fails the link with a metadata mismatch. The functions are
// declarations only and link to the originals.
ref struct CalculationData
{
	Query^ query;
	Solution^ solution;
	AbilityMap need;
	Map_t< Skill^, int > relevant;
	List_t< List_t< Decoration^ >^ > rel_decoration_map;
};

void GetInitialData( CalculationData^ data );

template< bool allow_bad, bool allow_detrimental >
void CalculateDecorations( CalculationData^ data );

cliext::pair< int, int > GetScore( Decoration^ decoration, CalculationData^ data, const unsigned actual_good );

// Solution's private members, through reflection.
namespace LegacySolution
{
	inline System::Reflection::BindingFlags PrivateInstance()
	{
		return System::Reflection::BindingFlags::NonPublic | System::Reflection::BindingFlags::Instance;
	}

	inline void SetData( Solution^ solution, CalculationData^ data )
	{
		Solution::typeid->GetField( L"data", PrivateInstance() )->SetValue( solution, data );
	}

	inline CalculationData^ GetData( Solution^ solution )
	{
		return safe_cast< CalculationData^ >( Solution::typeid->GetField( L"data", PrivateInstance() )->GetValue( solution ) );
	}

	// Calls a parameterless private method. Invoke wraps whatever the method
	// throws in a TargetInvocationException: rethrow the original, so callers
	// record the same exception type the real MatchesQuery would throw.
	inline System::Object^ Call( Solution^ solution, System::String^ method )
	{
		System::Reflection::MethodInfo^ info = Solution::typeid->GetMethod( method, PrivateInstance() );
		if( !info )
			throw gcnew System::MissingMethodException( L"Solution", method );
		try
		{
			return info->Invoke( solution, nullptr );
		}
		catch( System::Reflection::TargetInvocationException^ error )
		{
			System::Runtime::ExceptionServices::ExceptionDispatchInfo::Capture( error->InnerException )->Throw();
			throw;
		}
	}

	inline bool CallBool( Solution^ solution, System::String^ method )
	{
		return safe_cast< bool >( Call( solution, method ) );
	}

	// The rel_decoration_map MatchesQuery builds (Solution.cpp:665-670).
	inline CalculationData^ NewData( Solution^ solution, Query^ query )
	{
		CalculationData^ data = gcnew CalculationData;
		data->query = query;
		data->solution = solution;
		for( int i = 0; i < 4; ++i )
			data->rel_decoration_map.Add( gcnew List_t< Decoration^ > );
		for each( Decoration^ deco in query->rel_decorations )
		{
			data->rel_decoration_map[ deco->slots_required ]->Add( deco );
		}
		return data;
	}
}
