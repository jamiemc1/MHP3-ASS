#pragma once

// L1 fixtures for charm import: both decryption layers and the charm records
// extracted from each character, following ImportCharms.h without its UI.
namespace SaveDump
{
	void Write( System::String^ save_path, System::String^ out_path );
}
