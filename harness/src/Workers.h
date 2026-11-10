#pragma once

ref struct Armor;
ref struct Charm;
ref struct Query;
ref struct Solution;

// The workers a search starts and the jobs they run, shared by every command
// that replays Form1::StartSearch and backgroundWorker1_DoWork.
namespace Workers
{
	// CharmDatabase::LoadCustom(), CharmDatabase.cpp:108-168, reading the lines
	// from the corpus instead of Data/mycharms.txt. Malformed lines throw
	// instead of showing a message box; illegal charms are skipped and counted,
	// as the GUI skips them. Returns the number skipped.
	int LoadMyCharms( array< System::Object^ >^ lines );

	// The index of the GUI's charm drop-down for a corpus charm_mode.
	int CharmSelectIndex( System::String^ charm_mode );

	// The charm template of each worker Form1::StartSearch starts, in start order
	// (Form1.h:1273-1373). A nullptr entry is a worker searching without a charm.
	System::Collections::Generic::List< Charm^ >^ WorkerCharms( Query^ query, const int charm_select );

	// backgroundWorker1_DoWork gives an empty relevant-armour slot one nullptr
	// piece (Form1.h:1865-1869). It changes the shared query, so every later
	// worker and reader sees the nullptr too.
	void AddEmptySlotPieces( Query^ query );

	// One job as backgroundWorker1_DoWork builds it (Form1.h:1904-1912): the
	// five armour pieces (head, body, arms, waist, legs; nullptr for an empty
	// slot) and a deep copy of the worker's charm template.
	Solution^ NewJob( array< Armor^ >^ armors, Charm^ charm_template );

	// Form1::backgroundWorker1_DoWork, Form1.h:1852-1930, without progress
	// reporting or cancellation. The GUI hands solutions over in batches, but
	// always in this order.
	System::Collections::Generic::List< Solution^ >^ RunWorker( Query^ query, Charm^ charm_template );
}
