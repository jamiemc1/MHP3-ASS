#pragma once

ref struct Armor;
ref struct Solution;

// Form1's result collection (Form1.h:1691-1746): the lists a search fills and
// LoadConfig refills, and the de-duplication set only StartSearch clears.
ref class ResultSet
{
public:
	System::Collections::Generic::List< Solution^ > all_solutions, no_charm_solutions;
	// Insertion order is enumeration order: nothing is ever removed.
	System::Collections::Generic::Dictionary< System::String^, System::Collections::Generic::List< Solution^ >^ > charm_solution_map;

	// AddSolutions, Form1.h:1732-1746. Returns the solutions it kept, in the
	// order it appended them to all_solutions.
	System::Collections::Generic::List< Solution^ >^ AddSolutions( System::Collections::Generic::List< Solution^ >^ solutions );

	// AddSolution( String^, Solution^ ), Form1.h:1723-1730. False for a duplicate.
	bool AddSolution( System::String^ charm, Solution^ sol );

	// The lists LoadConfig clears before reading solutions (Form1.h:430-432).
	void ClearForLoad();

private:
	System::Collections::Generic::Dictionary< System::String^, System::Collections::Generic::Dictionary< __int64, bool >^ > existing_armor;

	__int64 HashArmor( System::Collections::Generic::List< Armor^ >% armors );
	bool SolutionExists( System::String^ charm, Solution^ sol );
};

// One solution line of Form1::SaveConfig, Form1.h:495-538 (without the newline).
System::String^ SolutionLine( Solution^ solution );
