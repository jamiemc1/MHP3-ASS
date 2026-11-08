#pragma once

ref struct Charm;
ref struct Query;

// The charm templates a search runs with, shared by every command that
// replays Form1::StartSearch.
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
}
