import re

from .types import Module, ResultInfo, ConsoleErrorInfo, ConsoleErrorField, BANNED_FIELD, WARNING_COLOR

"""
This file contains all currently known Switch result and error codes.
There may be inaccuracies here; we'll do our best to correct them
when we find out more about them.
A result code is a 32-bit integer returned when calling various commands in the
Switch's operating system, Horizon. Its breaks down like so:
 Bits | Description
-------------------
00-08 | Module
09-21 | Description
Module: A value indicating who raised the error or returned the result.
Description: A value indicating exactly what happened.
Unlike the 3DS, the Nintendo Switch does not provide a 'summary' or 'level'
field in result codes, so some artistic license was taken here to repurpose those
fields in our ResultInfo class to add additional information from sources
such as Atmosphere's libvapours and the Switchbrew wiki.
To add a module so the code understands it, simply add a new module number
to the 'modules' dictionary, with a Module variable as the value. If the module
has no known error codes, simply add a dummy Module instead (see the dict for
more info). See the various module variables for a more in-depth example
 on how to make one.
Once you've added a module, or you want to add a new result code to an existing
module, add a new description value (for Switch it's the final set of 4 digits after any dashes)
as the key, and a ResultInfo variable with a text description of the error or result.
You can also add a second string to the ResultInfo to designate a support URL if
one exists. Not all results or errors have support webpages.
Simple example of adding a module with a sample result code:
test = Module('test', {
    5: ResultInfo('test', 'https://example.com')
})
modules = {
    9999: test
}
Sources used to compile these results and information:
https://switchbrew.org/wiki/Error_codes
https://github.com/Atmosphere-NX/Atmosphere/tree/master/libraries/libvapours/include/vapours/results
"""

kernel = Module('kernel', {
    7: ResultInfo('Out of sessions.'),
    14: ResultInfo('Invalid argument.'),
    33: ResultInfo('Not implemented.'),
    54: ResultInfo('Stop processing exception.'),
    57: ResultInfo('No synchronization object.'),
    59: ResultInfo('Termination requested.'),
    70: ResultInfo('No event.'),
    101: ResultInfo('Invalid size.'),
    102: ResultInfo('Invalid address.'),
    103: ResultInfo('Out of resources.'),
    104: ResultInfo('Out of memory.'),
    105: ResultInfo('Out of handles.'),
    106: ResultInfo('Invalid current memory state or permissions.'),
    108: ResultInfo('Invalid new memory permissions.'),
    110: ResultInfo('Invalid memory region.'),
    112: ResultInfo('Invalid thread priority.'),
    113: ResultInfo('Invalid processor core ID.'),
    114: ResultInfo('Invalid handle.'),
    115: ResultInfo('Invalid pointer.'),
    116: ResultInfo('Invalid combination.'),
    117: ResultInfo('Timed out.'),
    118: ResultInfo('Cancelled.'),
    119: ResultInfo('Out of range.'),
    120: ResultInfo('Invalid enum value.'),
    121: ResultInfo('Not found.'),
    122: ResultInfo('Busy or already registered.'),
    123: ResultInfo('Session closed.'),
    124: ResultInfo('Not handled.'),
    125: ResultInfo('Invalid state.'),
    126: ResultInfo('Reserved used.'),
    127: ResultInfo('Not supported.'),
    128: ResultInfo('Debug.'),
    129: ResultInfo('Thread not owned.'),
    131: ResultInfo('Port closed.'),
    132: ResultInfo('Limit reached.'),
    133: ResultInfo('Invalid memory pool.'),
    258: ResultInfo('Receive list broken.'),
    259: ResultInfo('Out of address space.'),
    260: ResultInfo('Message too large.'),
    517: ResultInfo('Invalid process ID.'),
    518: ResultInfo('Invalid thread ID.'),
    519: ResultInfo('Invalid thread ID (svcGetDebugThreadParam).'),
    520: ResultInfo('Process terminated.')
})

fs = Module('fs', {
    1: ResultInfo('Path not found.'),
    2: ResultInfo('Path already exists.'),
    7: ResultInfo('Target locked (already in use).'),
    8: ResultInfo('Directory not empty.'),
    35: ResultInfo('Not enough free space on CAL0 partition.'),
    36: ResultInfo('Not enough free space on SAFE partition.'),
    37: ResultInfo('Not enough free space on USER partition.'),
    38: ResultInfo('Not enough free space on SYSTEM partition.'),
    39: ResultInfo('Not enough free space on SD card.'),
    50: ResultInfo('NCA is older than version 3, or NCA SDK version is < 0.11.0.0.'),
    60: ResultInfo('Mount name already exists.'),
    1001: ResultInfo('Process does not have RomFS.'),
    1002: ResultInfo('Target not found.'),
    2001: ResultInfo('SD card not present.'),
    2520: ResultInfo('Game Card is not inserted.'),
    2522: ResultInfo('Attempted to process an AsicHandler command in initial mode.'),
    2540: ResultInfo('Attempted to read from the secure Game Card partition in normal mode.'),
    2541: ResultInfo('Attempted to read from the normal Game Card partition in secure mode.'),
    2542: ResultInfo('Attempted a read that spanned both the normal and secure Game Card partitions.'),
    2544: ResultInfo('Game Card initial data hash doesn\'t match the initial data hash in the card header.'),
    2545: ResultInfo('Game Card initial data reserved area is not all zeroes.'),
    2546: ResultInfo('Game Card certificate kek index doesn\'t match card header kek index.'),
    2551: ResultInfo('Unable to read card header on Game Card initialization.'),
    2565: ResultInfo('Encountered SDMMC error in write operation.'),
    2600: ResultInfo('Attempted to switch Lotus state machine to secure mode from a mode other than normal mode.'),
    2601: ResultInfo('Attempted to switch Lotus state machine to normal mode from a mode other than initial mode.'),
    2602: ResultInfo('Attempted to switch Lotus state machine to write mode from a mode other than normal mode.'),
    2634: ResultInfo('Error processing Lotus command SetUserAsicFirmware.'),
    2637: ResultInfo('Error processing Lotus command GetAsicCert.'),
    2640: ResultInfo('Error processing Lotus command SetEmmcEmbeddedSocCertificate.'),
    2645: ResultInfo('Error processing Lotus command GetAsicEncryptedMessage.'),
    2646: ResultInfo('Error processing Lotus command SetLibraryEncryptedMessage.'),
    2651: ResultInfo('Error processing Lotus command GetAsicAuthenticationData.'),
    2652: ResultInfo('Error processing Lotus command SetAsicAuthenticationDataHash.'),
    2653: ResultInfo('Error processing Lotus command SetLibraryAuthenticationData.'),
    2654: ResultInfo('Error processing Lotus command GetLibraryAuthenticationDataHash.'),
    2657: ResultInfo('Error processing Lotus command ExchangeRandomValuesInSecureMode.'),
    2668: ResultInfo('Error calling nn::gc::detail::GcCrypto::GenerateRandomBytes.'),
    2671: ResultInfo('Error processing Lotus command ReadAsicRegister.'),
    2672: ResultInfo('Error processing Lotus command GetGameCardIdSet.'),
    2674: ResultInfo('Error processing Lotus command GetCardHeader.'),
    2676: ResultInfo('Error processing Lotus command GetCardKeyArea.'),
    2677: ResultInfo('Error processing Lotus command ChangeDebugMode.'),
    2678: ResultInfo('Error processing Lotus command GetRmaInformation.'),
    2692: ResultInfo('Tried sending Lotus card command Refresh when not in secure mode.'),
    2693: ResultInfo('Tried sending Lotus card command when not in correct mode.'),
    2731: ResultInfo('Error processing Lotus card command ReadId1.'),
    2732: ResultInfo('Error processing Lotus card command ReadId2.'),
    2733: ResultInfo('Error processing Lotus card command ReadId3.'),
    2735: ResultInfo('Error processing Lotus card command ReadPage.'),
    2737: ResultInfo('Error processing Lotus card command WritePage.'),
    2738: ResultInfo('Error processing Lotus card command Refresh.'),
    2742: ResultInfo('Error processing Lotus card command ReadCrc.'),
    2743: ResultInfo('Error processing Lotus card command Erase or UnlockForceErase.'),
    2744: ResultInfo('Error processing Lotus card command ReadDevParam.'),
    2745: ResultInfo('Error processing Lotus card command WriteDevParam.'),
    2904: ResultInfo('Id2Normal did not match the value in the buffer returned by ChangeDebugMode.'),
    2905: ResultInfo('Id1Normal did not match Id1Writer when switching gamecard to write mode.'),
    2906: ResultInfo('Id2Normal did not match Id2Writer when switching gamecard to write mode.'),
    2954: ResultInfo('Invalid Game Card handle.'),
    2960: ResultInfo('Invalid gamecard handle when opening normal gamecard partition.'),
    2961: ResultInfo('Invalid gamecard handle when opening secure gamecard partition.'),
    3001: ResultInfo('Not implemented.'),
    3002: ResultInfo('Unsupported version.'),
    3003: ResultInfo('File or directory already exists.'),
    3005: ResultInfo('Out of range.'),
    3100: ResultInfo('System partition not ready.'),
    3201: ResultInfo('Memory allocation failure related to FAT filesystem code.'),
    3203: ResultInfo('Memory allocation failure related to FAT filesystem code.'),
    3204: ResultInfo('Memory allocation failure related to FAT filesystem code.'),
    3206: ResultInfo('Memory allocation failure related to FAT filesystem code.'),
    3208: ResultInfo('Memory allocation failure related to FAT filesystem code.'),
    3211: ResultInfo('Allocation failure in FileSystemAccessorA.'),
    3212: ResultInfo('Allocation failure in FileSystemAccessorB.'),
    3213: ResultInfo('Allocation failure in ApplicationA.'),
    3215: ResultInfo('Allocation failure in BisA.'),
    3216: ResultInfo('Allocation failure in BisB.'),
    3217: ResultInfo('Allocation failure in BisC.'),
    3218: ResultInfo('Allocation failure in CodeA.'),
    3219: ResultInfo('Allocation failure in ContentA.'),
    3220: ResultInfo('Allocation failure in ContentStorageA.'),
    3221: ResultInfo('Allocation failure in ContentStorageB.'),
    3222: ResultInfo('Allocation failure in DataA.'),
    3223: ResultInfo('Allocation failure in DataB.'),
    3224: ResultInfo('Allocation failure in DeviceSaveDataA.'),
    3225: ResultInfo('Allocation failure in GameCardA'),
    3226: ResultInfo('Allocation failure in GameCardB'),
    3227: ResultInfo('Allocation failure in GameCardC'),
    3228: ResultInfo('Allocation failure in GameCardD'),
    3232: ResultInfo('Allocation failure in ImageDirectoryA.'),
    3244: ResultInfo('Allocation failure in SDCardA.'),
    3245: ResultInfo('Allocation failure in SDCardB.'),
    3246: ResultInfo('Allocation failure in SystemSaveDataA.'),
    3247: ResultInfo('Allocation failure in RomFsFileSystemA.'),
    3248: ResultInfo('Allocation failure in RomFsFileSystemB.'),
    3249: ResultInfo('Allocation failure in RomFsFileSystemC.'),
    3256: ResultInfo('Allocation failure in FilesystemProxyCoreImplD.'),
    3257: ResultInfo('Allocation failure in FilesystemProxyCoreImplE.'),
    3280: ResultInfo('Allocation failure in PartitionFileSystemCreatorA.'),
    3281: ResultInfo('Allocation failure in RomFileSystemCreatorA.'),
    3288: ResultInfo('Allocation failure in StorageOnNcaCreatorA.'),
    3289: ResultInfo('Allocation failure in StorageOnNcaCreatorB.'),
    3294: ResultInfo('Allocation failure in SystemBuddyHeapA.'),
    3295: ResultInfo('Allocation failure in SystemBufferManagerA.'),
    3296: ResultInfo('Allocation failure in BlockCacheBufferedStorageA.'),
    3297: ResultInfo('Allocation failure in BlockCacheBufferedStorageB.'),
    3304: ResultInfo('Allocation failure in IntegrityVerificationStorageA.'),
    3305: ResultInfo('Allocation failure in IntegrityVerificationStorageB.'),
    3321: ResultInfo('Allocation failure in DirectorySaveDataFileSystem.'),
    3341: ResultInfo('Allocation failure in NcaFileSystemDriverI.'),
    3347: ResultInfo('Allocation failure in PartitionFileSystemA.'),
    3348: ResultInfo('Allocation failure in PartitionFileSystemB.'),
    3349: ResultInfo('Allocation failure in PartitionFileSystemC.'),
    3350: ResultInfo('Allocation failure in PartitionFileSystemMetaA.'),
    3351: ResultInfo('Allocation failure in PartitionFileSystemMetaB.'),
    3355: ResultInfo('Allocation failure in SubDirectoryFileSystem.'),
    3359: ResultInfo('Out of memory.'),
    3360: ResultInfo('Out of memory.'),
    3363: ResultInfo('Allocation failure in NcaReaderA.'),
    3365: ResultInfo('Allocation failure in RegisterA.'),
    3366: ResultInfo('Allocation failure in RegisterB.'),
    3367: ResultInfo('Allocation failure in PathNormalizer.'),
    3375: ResultInfo('Allocation failure in DbmRomKeyValueStorage.'),
    3377: ResultInfo('Allocation failure in RomFsFileSystemE.'),
    3386: ResultInfo('Allocation failure in ReadOnlyFileSystemA.'),
    3399: ResultInfo('Allocation failure in AesCtrCounterExtendedStorageA.'),
    3400: ResultInfo('Allocation failure in AesCtrCounterExtendedStorageB.'),
    3407: ResultInfo('Allocation failure in FileSystemInterfaceAdapter.'),
    3411: ResultInfo('Allocation failure in BufferedStorageA.'),
    3412: ResultInfo('Allocation failure in IntegrityRomFsStorageA.'),
    3420: ResultInfo('Allocation failure in New.'),
    3422: ResultInfo('Allocation failure in MakeUnique.'),
    3423: ResultInfo('Allocation failure in AllocateShared.'),
    3424: ResultInfo('Allocation failure in PooledBufferNotEnoughSize.'),
    4000: ResultInfo('The data is corrupted.'),
    4002: ResultInfo('Unsupported ROM version.'),
    4012: ResultInfo('Invalid AesCtrCounterExtendedEntryOffset.'),
    4013: ResultInfo('Invalid AesCtrCounterExtendedTableSize.'),
    4014: ResultInfo('Invalid AesCtrCounterExtendedGeneration.'),
    4015: ResultInfo('Invalid AesCtrCounterExtendedOffset.'),
    4022: ResultInfo('Invalid IndirectEntryOffset.'),
    4023: ResultInfo('Invalid IndirectEntryStorageIndex.'),
    4024: ResultInfo('Invalid IndirectStorageSize.'),
    4025: ResultInfo('Invalid IndirectVirtualOffset.'),
    4026: ResultInfo('Invalid IndirectPhysicalOffset.'),
    4027: ResultInfo('Invalid IndirectStorageIndex.'),
    4032: ResultInfo('Invalid BucketTreeSignature.'),
    4033: ResultInfo('Invalid BucketTreeEntryCount.'),
    4034: ResultInfo('Invalid BucketTreeNodeEntryCount.'),
    4035: ResultInfo('Invalid BucketTreeNodeOffset.'),
    4036: ResultInfo('Invalid BucketTreeEntryOffset.'),
    4037: ResultInfo('Invalid BucketTreeEntrySetOffset.'),
    4038: ResultInfo('Invalid BucketTreeNodeIndex.'),
    4039: ResultInfo('Invalid BucketTreeVirtualOffset.'),
    4052: ResultInfo('ROM NCA filesystem type is invalid.'),
    4053: ResultInfo('ROM ACID file size is invalid.'),
    4054: ResultInfo('ROM ACID size is invalid.'),
    4055: ResultInfo('ROM ACID is invalid.'),
    4056: ResultInfo('ROM ACID verification failed.'),
    4057: ResultInfo('ROM NCA signature is invalid.'),
    4058: ResultInfo('ROM NCA header signature 1 verification failed.'),
    4059: ResultInfo('ROM NCA header signature 2 verification failed.'),
    4060: ResultInfo('ROM NCA FS header hash verification failed.'),
    4061: ResultInfo('ROM NCA key index is invalid.'),
    4062: ResultInfo('ROM NCA FS header hash type is invalid.'),
    4063: ResultInfo('ROM NCA FS header encryption type is invalid.'),
    4070: ResultInfo('ROM data is corrupted.'),
    4072: ResultInfo('Invalid ROM hierarchical SHA256 block size.'),
    4073: ResultInfo('Invalid ROM hierarchical SHA256 layer count.'),
    4074: ResultInfo('ROM hierarchical SHA256 BaseStorage is too large.'),
    4075: ResultInfo('ROM hierarchical SHA256 hash verification failed.'),
    4142: ResultInfo('Incorrect ROM integrity verification magic.'),
    4143: ResultInfo('Invalid ROM0 hash.'),
    4144: ResultInfo('ROM non-real data verification failed.'),
    4145: ResultInfo('Invalid ROM hierarchical integrity verification layer count.'),
    4151: ResultInfo('Cleared ROM real data verification failed.'),
    4152: ResultInfo('Uncleared ROM real data verification failed.'),
    4153: ResultInfo('Invalid ROM0 hash.'),
    4182: ResultInfo('Invalid ROM SHA256 partition hash target.'),
    4183: ResultInfo('ROM SHA256 partition hash verification failed.'),
    4184: ResultInfo('ROM partition signature verification failed.'),
    4185: ResultInfo('ROM SHA256 partition signature verification failed.'),
    4186: ResultInfo('Invalid ROM partition entry offset.'),
    4187: ResultInfo('Invalid ROM SHA256 partition metadata size.'),
    4202: ResultInfo('ROM GPT header verification failed.'),
    4242: ResultInfo('ROM host entry corrupted.'),
    4243: ResultInfo('ROM host file data corrupted.'),
    4244: ResultInfo('ROM host file corrupted.'),
    4245: ResultInfo('Invalid ROM host handle.'),
    4262: ResultInfo('Invalid ROM allocation table block.'),
    4263: ResultInfo('Invalid ROM key value list element index.'),
    4318: ResultInfo('Invalid save data filesystem magic (valid magic is SAVE in ASCII).'),
    4508: ResultInfo('NcaBaseStorage is out of Range A.'),
    4509: ResultInfo('NcaBaseStorage is out of Range B.'),
    4512: ResultInfo('Invalid NCA filesystem type.'),
    4513: ResultInfo('Invalid ACID file size.'),
    4514: ResultInfo('Invalid ACID size.'),
    4515: ResultInfo('Invalid ACID.'),
    4516: ResultInfo('ACID verification failed.'),
    4517: ResultInfo('Invalid NCA signature.'),
    4518: ResultInfo('NCA header signature 1 verification failed.'),
    4519: ResultInfo('NCA header signature 2 verification failed.'),
    4520: ResultInfo('NCA FS header hash verification failed.'),
    4521: ResultInfo('Invalid NCA key index.'),
    4522: ResultInfo('Invalid NCA FS header hash type.'),
    4523: ResultInfo('Invalid NCA FS header encryption type.'),
    4524: ResultInfo('Redirection BKTR table size is negative.'),
    4525: ResultInfo('Encryption BKTR table size is negative.'),
    4526: ResultInfo('Redirection BKTR table end offset is past the Encryption BKTR table start offset.'),
    4527: ResultInfo('NCA path used with the wrong program ID.'),
    4528: ResultInfo('NCA header value is out of range.'),
    4529: ResultInfo('NCA FS header value is out of range.'),
    4530: ResultInfo('NCA is corrupted.'),
    4532: ResultInfo('Invalid hierarchical SHA256 block size.'),
    4533: ResultInfo('Invalid hierarchical SHA256 layer count.'),
    4534: ResultInfo('Hierarchical SHA256 base storage is too large.'),
    4535: ResultInfo('Hierarchical SHA256 hash verification failed.'),
    4543: ResultInfo('Invalid NCA header 1 signature key generation.'),
    4602: ResultInfo('Incorrect integrity verification magic.'),
    4603: ResultInfo('Invalid zero hash.'),
    4604: ResultInfo('Non-real data verification failed.'),
    4605: ResultInfo('Invalid hierarchical integrity verification layer count.'),
    4612: ResultInfo('Cleared real data verification failed.'),
    4613: ResultInfo('Uncleared real data verification failed.'),
    4642: ResultInfo('Invalid SHA256 partition hash target.'),
    4643: ResultInfo('SHA256 partition hash verification failed.'),
    4644: ResultInfo('Partition signature verification failed.'),
    4645: ResultInfo('SHA256 partition signature verification failed.'),
    4646: ResultInfo('Invalid partition entry offset.'),
    4647: ResultInfo('Invalid SHA256 partition metadata size.'),
    4662: ResultInfo('GPT header verification failed.'),
    4684: ResultInfo('Invalid FAT file number.'),
    4686: ResultInfo('Invalid FAT format for BIS USER partition.'),
    4687: ResultInfo('Invalid FAT format for BIS SYSTEM partition.'),
    4688: ResultInfo('Invalid FAT format for BIS SAFE partition.'),
    4689: ResultInfo('Invalid FAT format for BIS PRODINFOF partition.'),
    4702: ResultInfo('Host entry is corrupted.'),
    4703: ResultInfo('Host file data is corrupted.'),
    4704: ResultInfo('Host file is corrupted.'),
    4705: ResultInfo('Invalid host handle.'),
    4722: ResultInfo('Invalid allocation table block.'),
    4723: ResultInfo('Invalid key value list element index.'),
    4743: ResultInfo('Corrupted NAX0 header.'),
    4744: ResultInfo('Invalid NAX0 magic number.'),
    4781: ResultInfo('Game Card logo data is corrupted.'),
    5121: ResultInfo('Invalid FAT size.'),
    5122: ResultInfo('Invalid FAT BPB (BIOS Parameter Block).'),
    5123: ResultInfo('Invalid FAT parameter.'),
    5124: ResultInfo('Invalid FAT sector.'),
    5125: ResultInfo('Invalid FAT sector.'),
    5126: ResultInfo('Invalid FAT sector.'),
    5127: ResultInfo('Invalid FAT sector.'),
    5301: ResultInfo('Mount point not found.'),
    5315: ResultInfo('Unexpected InAesCtrStorageA.'),
    5317: ResultInfo('Unexpected InAesXtsStorageA.'),
    5319: ResultInfo('Unexpected InFindFileSystemA.'),
    6000: ResultInfo('Precondition violation.'),
    6001: ResultInfo('Invalid argument.'),
    6003: ResultInfo('Path is too long.'),
    6004: ResultInfo('Invalid character.'),
    6005: ResultInfo('Invalid path format.'),
    6006: ResultInfo('Directory is unobtainable.'),
    6007: ResultInfo('Not normalized.'),
    6031: ResultInfo('The directory is not deletable.'),
    6032: ResultInfo('The directory is not renameable.'),
    6033: ResultInfo('The path is incompatible.'),
    6034: ResultInfo('Rename to other filesystem.'),  # 'Attempted to rename to other filesystem.'?
    6061: ResultInfo('Invalid offset.'),
    6062: ResultInfo('Invalid size.'),
    6063: ResultInfo('Argument is nullptr.'),
    6064: ResultInfo('Invalid alignment.'),
    6065: ResultInfo('Invalid mount name.'),
    6066: ResultInfo('Extension size is too large.'),
    6067: ResultInfo('Extension size is invalid.'),
    6072: ResultInfo('Invalid open mode.'),
    6081: ResultInfo('Invalid savedata state.'),
    6082: ResultInfo('Invalid savedata space ID.'),
    6201: ResultInfo('File extension without open mode AllowAppend.'),
    6202: ResultInfo('Reads are not permitted.'),
    6203: ResultInfo('Writes are not permitted.'),
    6300: ResultInfo('Operation not supported.'),
    6301: ResultInfo('A specified filesystem has no MultiCommitTarget when doing a multi-filesystem commit.'),
    6302: ResultInfo('Attempted to resize a nn::fs::SubStorage or BufferedStorage that is marked as non-resizable.'),
    6303: ResultInfo(
        'Attempted to resize a nn::fs::SubStorage or BufferedStorage when the SubStorage ends before the base storage.'),
    6304: ResultInfo('Attempted to call nn::fs::MemoryStorage::SetSize.'),
    6305: ResultInfo('Invalid Operation ID in nn::fs::MemoryStorage::OperateRange.'),
    6306: ResultInfo('Invalid Operation ID in nn::fs::FileStorage::OperateRange.'),
    6307: ResultInfo('Invalid Operation ID in nn::fs::FileHandleStorage::OperateRange.'),
    6308: ResultInfo('Invalid Operation ID in nn::fssystem::SwitchStorage::OperateRange.'),
    6309: ResultInfo('Invalid Operation ID in nn::fs::detail::StorageServiceObjectAdapter::OperateRange.'),
    6310: ResultInfo('Attempted to call nn::fssystem::AesCtrCounterExtendedStorage::Write.'),
    6311: ResultInfo('Attempted to call nn::fssystem::AesCtrCounterExtendedStorage::SetSize.'),
    6312: ResultInfo('Invalid Operation ID in nn::fssystem::AesCtrCounterExtendedStorage::OperateRange.'),
    6313: ResultInfo('Attempted to call nn::fssystem::AesCtrStorageExternal::Write.'),
    6314: ResultInfo('Attempted to call nn::fssystem::AesCtrStorageExternal::SetSize.'),
    6315: ResultInfo('Attempted to call nn::fssystem::AesCtrStorage::SetSize.'),
    6316: ResultInfo('Attempted to call nn::fssystem::save::HierarchicalIntegrityVerificationStorage::SetSize.'),
    6317: ResultInfo('Attempted to call nn::fssystem::save::HierarchicalIntegrityVerificationStorage::OperateRange.'),
    6318: ResultInfo('Attempted to call nn::fssystem::save::IntegrityVerificationStorage::SetSize.'),
    6319: ResultInfo(
        'Attempted to invalidate the cache of a RomFs IVFC storage in nn::fssystem::save::IntegrityVerificationStorage::OperateRange.'),
    6320: ResultInfo('Invalid Operation ID in nn::fssystem::save::IntegrityVerificationStorage::OperateRange.'),
    6321: ResultInfo('Attempted to call nn::fssystem::save::BlockCacheBufferedStorage::SetSize.'),
    6322: ResultInfo(
        'Attempted to invalidate the cache of something other than a savedata IVFC storage in nn::fssystem::save::BlockCacheBufferedStorage::OperateRange.'),
    6323: ResultInfo('Invalid Operation ID in nn::fssystem::save::BlockCacheBufferedStorage::OperateRange.'),
    6324: ResultInfo('Attempted to call nn::fssystem::IndirectStorage::Write.'),
    6325: ResultInfo('Attempted to call nn::fssystem::IndirectStorage::SetSize.'),
    6326: ResultInfo('Invalid Operation ID in nn::fssystem::IndirectStorage::OperateRange.'),
    6327: ResultInfo('Attempted to call nn::fssystem::SparseStorage::ZeroStorage::Write.'),
    6328: ResultInfo('Attempted to call nn::fssystem::SparseStorage::ZeroStorage::SetSize.'),
    6329: ResultInfo('Attempted to call nn::fssystem::HierarchicalSha256Storage::SetSize.'),
    6330: ResultInfo('Attempted to call nn::fssystem::ReadOnlyBlockCacheStorage::Write.'),
    6331: ResultInfo('Attempted to call nn::fssystem::ReadOnlyBlockCacheStorage::SetSize.'),
    6332: ResultInfo('Attempted to call nn::fssystem::IntegrityRomFsStorage::SetSize.'),
    6333: ResultInfo('Attempted to call nn::fssystem::save::DuplexStorage::SetSize.'),
    6334: ResultInfo('Invalid Operation ID in nn::fssystem::save::DuplexStorage::OperateRange.'),
    6335: ResultInfo('Attempted to call nn::fssystem::save::HierarchicalDuplexStorage::SetSize.'),
    6336: ResultInfo('Attempted to call nn::fssystem::save::RemapStorage::GetSize.'),
    6337: ResultInfo('Attempted to call nn::fssystem::save::RemapStorage::SetSize.'),
    6338: ResultInfo('Invalid Operation ID in nn::fssystem::save::RemapStorage::OperateRange.'),
    6339: ResultInfo('Attempted to call nn::fssystem::save::IntegritySaveDataStorage::SetSize.'),
    6340: ResultInfo('Invalid Operation ID in nn::fssystem::save::IntegritySaveDataStorage::OperateRange.'),
    6341: ResultInfo('Attempted to call nn::fssystem::save::JournalIntegritySaveDataStorage::SetSize.'),
    6342: ResultInfo('Invalid Operation ID in nn::fssystem::save::JournalIntegritySaveDataStorage::OperateRange.'),
    6343: ResultInfo('Attempted to call nn::fssystem::save::JournalStorage::GetSize.'),
    6344: ResultInfo('Attempted to call nn::fssystem::save::JournalStorage::SetSize.'),
    6345: ResultInfo('Invalid Operation ID in nn::fssystem::save::JournalStorage::OperateRange.'),
    6346: ResultInfo('Attempted to call nn::fssystem::save::UnionStorage::SetSize.'),
    6347: ResultInfo('Attempted to call nn::fssystem::dbm::AllocationTableStorage::SetSize.'),
    6348: ResultInfo('Attempted to call nn::fssrv::fscreator::WriteOnlyGameCardStorage::Read.'),
    6349: ResultInfo('Attempted to call nn::fssrv::fscreator::WriteOnlyGameCardStorage::SetSize.'),
    6350: ResultInfo('Attempted to call nn::fssrv::fscreator::ReadOnlyGameCardStorage::Write.'),
    6351: ResultInfo('Attempted to call nn::fssrv::fscreator::ReadOnlyGameCardStorage::SetSize.'),
    6352: ResultInfo('Invalid Operation ID in nn::fssrv::fscreator::ReadOnlyGameCardStorage::OperateRange.'),
    6353: ResultInfo('Attempted to call SdStorage::SetSize.'),
    6354: ResultInfo('Invalid Operation ID in SdStorage::OperateRange.'),
    6355: ResultInfo('Invalid Operation ID in nn::fat::FatFile::DoOperateRange.'),
    6356: ResultInfo('Invalid Operation ID in nn::fssystem::StorageFile::DoOperateRange.'),
    6357: ResultInfo('Attempted to call nn::fssystem::ConcatenationFile::SetSize.'),
    6358: ResultInfo('Attempted to call nn::fssystem::ConcatenationFile::OperateRange.'),
    6359: ResultInfo('Invalid Query ID in nn::fssystem::ConcatenationFileSystem::DoQueryEntry.'),
    6360: ResultInfo('Invalid Operation ID in nn::fssystem::ConcatenationFile::DoOperateRange.'),
    6361: ResultInfo('Attempted to call nn::fssystem::ZeroBitmapFile::SetSize.'),
    6362: ResultInfo('Invalid Operation ID in nn::fs::detail::FileServiceObjectAdapter::DoOperateRange.'),
    6363: ResultInfo('Invalid Operation ID in nn::fssystem::AesXtsFile::DoOperateRange.'),
    6364: ResultInfo('Attempted to modify a nn::fs::RomFsFileSystem.'),
    6365: ResultInfo('Attempted to call nn::fs::RomFsFileSystem::DoCommitProvisionally.'),
    6366: ResultInfo('Attempted to query the space in a nn::fs::RomFsFileSystem.'),
    6367: ResultInfo('Attempted to modify a nn::fssystem::RomFsFile.'),
    6368: ResultInfo('Invalid Operation ID in nn::fssystem::RomFsFile::DoOperateRange.'),
    6369: ResultInfo('Attempted to modify a nn::fs::ReadOnlyFileSystemTemplate.'),
    6370: ResultInfo('Attempted to call nn::fs::ReadOnlyFileSystemTemplate::DoCommitProvisionally.'),
    6371: ResultInfo('Attempted to query the space in a nn::fs::ReadOnlyFileSystemTemplate.'),
    6372: ResultInfo('Attempted to modify a nn::fs::ReadOnlyFileSystemFile.'),
    6373: ResultInfo('Invalid Operation ID in nn::fs::ReadOnlyFileSystemFile::DoOperateRange.'),
    6374: ResultInfo('UAttempted to modify a nn::fssystem::PartitionFileSystemCore.'),
    6375: ResultInfo('Attempted to call nn::fssystem::PartitionFileSystemCore::DoCommitProvisionally.'),
    6376: ResultInfo('Attempted to call nn::fssystem::PartitionFileSystemCore::PartitionFile::DoSetSize.'),
    6377: ResultInfo('Invalid Operation ID in nn::fssystem::PartitionFileSystemCore::PartitionFile::DoOperateRange.'),
    6378: ResultInfo('Invalid Operation ID in nn::fssystem::TmFileSystemFile::DoOperateRange.'),
    6379: ResultInfo(
        'Attempted to call unsupported functions in nn::fssrv::fscreator::SaveDataInternalStorageFileSystem, nn::fssrv::detail::SaveDataInternalStorageAccessor::PaddingFile or nn::fssystem::save::detail::SaveDataExtraDataInternalStorageFile.'),
    6382: ResultInfo('Attempted to call nn::fssystem::ApplicationTemporaryFileSystem::DoCommitProvisionally.'),
    6383: ResultInfo('Attempted to call nn::fssystem::SaveDataFileSystem::DoCommitProvisionally.'),
    6384: ResultInfo('Attempted to call nn::fssystem::DirectorySaveDataFileSystem::DoCommitProvisionally.'),
    6385: ResultInfo('Attempted to call nn::fssystem::ZeroBitmapHashStorageFile::Write.'),
    6386: ResultInfo('Attempted to call nn::fssystem::ZeroBitmapHashStorageFile::SetSize.'),
    6400: ResultInfo('Permission denied.'),
    6451: ResultInfo('Missing titlekey (required to mount content).'),
    6454: ResultInfo('Needs flush.'),
    6455: ResultInfo('File not closed.'),
    6456: ResultInfo('Directory not closed.'),
    6457: ResultInfo('Write-mode file not closed.'),
    6458: ResultInfo('Allocator already registered.'),
    6459: ResultInfo('Default allocator used.'),
    6461: ResultInfo('Allocator alignment violation.'),
    6465: ResultInfo('User does not exist.'),
    6602: ResultInfo('File not found.'),
    6603: ResultInfo('Directory not found.'),
    6705: ResultInfo('Buffer allocation failed.'),
    6706: ResultInfo('Mapping table full.'),
    6709: ResultInfo('Open count limit reached.'),
    6710: ResultInfo('Multicommit limit reached.'),
    6811: ResultInfo('Map is full.'),
    6902: ResultInfo('Not initialized.'),
    6905: ResultInfo('Not mounted.'),
    7902: ResultInfo('DBM key was not found.'),
    7903: ResultInfo('DBM file was not found.'),
    7904: ResultInfo('DBM directory was not found.'),
    7906: ResultInfo('DBM already exists.'),
    7907: ResultInfo('DBM key is full.'),
    7908: ResultInfo('DBM directory entry is full.'),
    7909: ResultInfo('DBM file entry is full.'),
    7910: ResultInfo('RomFs directory has no more child directories/files when iterating.'),
    7911: ResultInfo('DBM FindKey finished.'),
    7912: ResultInfo('DBM iteration finished.'),
    7914: ResultInfo('Invalid DBM operation.'),
    7915: ResultInfo('Invalid DBM path format.'),
    7916: ResultInfo('DBM directory name is too long.'),
    7917: ResultInfo('DBM filename is too long.')
}, {
    (30, 33): 'Not enough free space.',
    (34, 38): 'Not enough BIS free space.',
    (39, 45): 'Not enough free space.',
    (2000, 2499): 'Failed to access SD card.',
    (2500, 2999): 'Failed to access Game Card.',
    (3200, 3499): 'Allocation failed.',
    (3500, 3999): 'Failed to access eMMC.',
    # (4001, 4200): 'ROM is corrupted.',
    (4001, 4010): 'ROM is corrupted.',
    (4011, 4019): 'AES-CTR CounterExtendedStorage is corrupted.',
    (4021, 4029): 'Indirect storage is corrupted.',
    (4031, 4039): 'Bucket tree is corrupted.',
    (4041, 4050): 'ROM NCA is corrupted.',
    (4051, 4069): 'ROM NCA filesystem is corrupted.',
    (4071, 4079): 'ROM NCA hierarchical SHA256 storage is corrupted.',
    (4141, 4150): 'ROM integrity verification storage is corrupted.',
    (4151, 4159): 'ROM real data verification failed.',
    (4160, 4079): 'ROM integrity verification storage is corrupted.',
    (4181, 4199): 'ROM partition filesystem is corrupted.',
    (4201, 4219): 'ROM built-in storage is corrupted.',
    (4241, 4259): 'ROM host filesystem is corrupted.',
    (4261, 4279): 'ROM database is corrupted.',
    (4280, 4299): 'ROM is corrupted.',
    (4301, 4499): 'Savedata is corrupted.',
    (4501, 4510): 'NCA is corrupted.',
    (4511, 4529): 'NCA filesystem is corrupted.',
    (4531, 4539): 'NCA hierarchical SHA256 storage is corrupted.',
    (4540, 4599): 'NCA is corrupted.',
    (4601, 4610): 'Integrity verification storage is corrupted.',
    (4611, 4619): 'Real data verification failed.',
    (4620, 4639): 'Integrity verification storage is corrupted.',
    (4641, 4659): 'Partition filesystem is corrupted.',
    (4661, 4679): 'Built-in storage is corrupted.',
    (4681, 4699): 'FAT filesystem is corrupted.',
    (4701, 4719): 'Host filesystem is corrupted.',
    (4721, 4739): 'Database is corrupted.',
    (4741, 4759): 'AEX-XTS filesystem is corrupted.',
    (4761, 4769): 'Savedata transfer data is corrupted.',
    (4771, 4779): 'Signed system partition data is corrupted.',
    (4800, 4999): 'The data is corrupted.',
    (5000, 5999): 'Unexpected.',
    (6002, 6029): 'Invalid path.',
    (6030, 6059): 'Invalid path for operation.',
    (6080, 6099): 'Invalid enum value.',
    (6100, 6199): 'Invalid argument.',
    (6200, 6299): 'Invalid operation for open mode.',
    (6300, 6399): 'Unsupported operation.',
    (6400, 6449): 'Permission denied.',
    (6600, 6699): 'Not found.',
    (6700, 6799): 'Out of resources.',
    (6800, 6899): 'Mapping failed.',
    (6900, 6999): 'Bad state.',
    (7901, 7904): 'DBM not found.',
    (7910, 7912): 'DBM find finished.',
})

os = Module('os', {
    4: ResultInfo('Busy.'),
    8: ResultInfo('Out of memory.'),
    9: ResultInfo('Out of resources.'),
    12: ResultInfo('Out of virtual address space.'),
    13: ResultInfo('Resource limit reached.'),
    384: ResultInfo('File operation failed.'),
    500: ResultInfo('Out of handles.'),
    501: ResultInfo('Invalid handle.'),
    502: ResultInfo('Invalid CurrentMemory state.'),
    503: ResultInfo('Invalid TransferMemory state.'),
    504: ResultInfo('Invalid TransferMemory size.'),
    505: ResultInfo('Out of TransferMemory.'),
    506: ResultInfo('Out of address space.')
})

ncm = Module('ncm', {
    1: ResultInfo('Invalid ContentStorageBase.'),
    2: ResultInfo('Placeholder already exists.'),
    3: ResultInfo('Placeholder not found (issue related to the SD card in use).',
                  'https://en-americas-support.nintendo.com/app/answers/detail/a_id/22393/kw/2005-0003'),
    4: ResultInfo('Content already exists.'),
    5: ResultInfo('Content not found.'),
    7: ResultInfo('Content meta not found.'),
    8: ResultInfo('Allocation failed.'),
    12: ResultInfo('Unknown storage.'),
    100: ResultInfo('Invalid ContentStorage.'),
    110: ResultInfo('Invalid ContentMetaDatabase.'),
    130: ResultInfo('Invalid package format.'),
    140: ResultInfo('Invalid content hash.'),
    160: ResultInfo('Invalid install task state.'),
    170: ResultInfo('Invalid placeholder file.'),
    180: ResultInfo('Buffer is insufficient.'),
    190: ResultInfo('Cannot write to read-only ContentStorage.'),
    200: ResultInfo('Not enough install space.'),
    210: ResultInfo('System update was not found in package.'),
    220: ResultInfo('Content info not found.'),
    237: ResultInfo('Delta not found.'),
    240: ResultInfo('Invalid content metakey.'),
    251: ResultInfo('GameCardContentStorage is not active.'),
    252: ResultInfo('BuiltInSystemContentStorage is not active.'),
    253: ResultInfo('BuiltInUserContentStorage is not active.'),
    254: ResultInfo('SdCardContentStorage is not active.'),
    258: ResultInfo('UnknownContentStorage is not active.'),
    261: ResultInfo('GameCardContentMetaDatabase is not active.'),
    262: ResultInfo('BuiltInSystemMetaDatabase is not active.'),
    263: ResultInfo('BuiltInUserMetaDatabase is not active.'),
    264: ResultInfo('SdCardContentMetaDatabase is not active.'),
    268: ResultInfo('UnknownContentMetaDatabase is not active.'),
    291: ResultInfo('Create placeholder was cancelled.'),
    292: ResultInfo('Write placeholder was cancelled.'),
    280: ResultInfo('Ignorable install ticket failure.'),
    310: ResultInfo('ContentStorageBase not found.'),
    330: ResultInfo('List partially not committed.'),
    360: ResultInfo('Unexpected ContentMeta prepared.'),
    380: ResultInfo('Invalid firmware variation.'),
    8182: ResultInfo('Invalid offset.')
}, {
    (250, 258): 'Content storage is not active.',
    (260, 268): 'Content meta database is not active.',
    (290, 299): 'Install task was cancelled.',
    (8181, 8191): 'Invalid argument.'
})

lr = Module('lr', {
    2: ResultInfo('Program not found.'),
    3: ResultInfo('Data not found.'),
    4: ResultInfo('Unknown storage ID.'),
    5: ResultInfo('Access denied.'),
    6: ResultInfo('HTML document not found.'),
    7: ResultInfo('Add-on Content not found.'),
    8: ResultInfo('Control not found.'),
    9: ResultInfo('Legal information not found.'),
    10: ResultInfo('Debug program not found.'),
    90: ResultInfo('Too many registered paths.')
})

loader = Module('loader', {
    1: ResultInfo('Argument too long.'),
    2: ResultInfo('Too many arguments.'),
    3: ResultInfo('Meta is too large.'),
    4: ResultInfo('Invalid meta.'),
    5: ResultInfo('Invalid NSO.'),
    6: ResultInfo('Invalid path.'),
    7: ResultInfo('Too many processes.'),
    8: ResultInfo('Not pinned.'),
    9: ResultInfo('Invalid program ID.'),
    10: ResultInfo('Invalid version.'),
    11: ResultInfo('Invalid ACID signature.'),
    12: ResultInfo('Invalid NCA signature.'),
    51: ResultInfo('Insufficient address space.'),
    52: ResultInfo('Invalid NRO.'),
    53: ResultInfo('Invalid NRR.'),
    54: ResultInfo('Invalid signature.'),
    55: ResultInfo('Insufficient NRO registrations.'),
    56: ResultInfo('Insufficient NRR registrations.'),
    57: ResultInfo('NRO already loaded.'),
    81: ResultInfo('Unaligned NRR address.'),
    82: ResultInfo('Invalid NRR size.'),
    84: ResultInfo('NRR not loaded.'),
    85: ResultInfo('Not registered (bad NRR address).'),
    86: ResultInfo('Invalid session.'),
    87: ResultInfo('Invalid process (bad initialization).'),
    100: ResultInfo('Unknown capability (unknown ACI0 descriptor).'),
    103: ResultInfo('CapabilityKernelFlags is invalid.'),
    104: ResultInfo('CapabilitySyscallMask is invalid.'),
    106: ResultInfo('CapabilityMapRange is invalid.'),
    107: ResultInfo('CapabilityMapPage is invalid.'),
    111: ResultInfo('CapabilityInterruptPair is invalid.'),
    113: ResultInfo('CapabilityApplicationType is invalid.'),
    114: ResultInfo('CapabilityKernelVersion is invalid.'),
    115: ResultInfo('CapabilityHandleTable is invalid.'),
    116: ResultInfo('CapabilityDebugFlags is invalid.'),
    200: ResultInfo('Internal error.')
})

sf = Module('sf', {
    1: ResultInfo('Not supported.'),
    3: ResultInfo('Precondition violation.'),
    202: ResultInfo('Invalid header size.'),
    211: ResultInfo('Invalid in header.'),
    212: ResultInfo('Invalid out header.'),
    221: ResultInfo('Unknown command ID.'),
    232: ResultInfo('Invalid out raw size.'),
    235: ResultInfo('Invalid number of in objects.'),
    236: ResultInfo('Invalid number of out objects.'),
    239: ResultInfo('Invalid in object.'),
    261: ResultInfo('Target not found.'),
    301: ResultInfo('Out of domain entries.'),
    800: ResultInfo('Request invalidated.'),
    802: ResultInfo('Request invalidated by user.'),
    812: ResultInfo('Request deferred by user.'),
}, {
    (800, 809): 'Request invalidated.',
                (810, 819): 'Request deferred.',
                (820, 899): 'Request context changed.'
})

hipc = Module('hipc', {
    1: ResultInfo('Unsupported operation.'),
    102: ResultInfo('Out of session memory.'),
    (131, 139): ResultInfo('Out of sessions.'),
    141: ResultInfo('Pointer buffer is too small.'),
    200: ResultInfo('Out of domains (session doesn\'t support domains).'),
    301: ResultInfo('Session closed.'),
    402: ResultInfo('Invalid request size.'),
    403: ResultInfo('Unknown command type.'),
    420: ResultInfo('Invalid CMIF request.'),
    491: ResultInfo('Target is not a domain.'),
    492: ResultInfo('Domain object was not found.')
}, {
    (100, 299): 'Out of resources.'
})

dmnt = Module('dmnt', {
    1: ResultInfo('Unknown error.'),
    2: ResultInfo('Debugging is disabled.'),

    # atmosphere extension errors
    6500: ResultInfo('Not attached.'),
    6501: ResultInfo('Buffer is null.'),
    6502: ResultInfo('Buffer is invalid.'),
    6503: ResultInfo('ID is unknown.'),
    6504: ResultInfo('Out of resources.'),
    6505: ResultInfo('Cheat is invalid.'),
    6506: ResultInfo('Cheat cannot be disabled.'),
    6600: ResultInfo('Width is invalid.'),
    6601: ResultInfo('Address already exists.'),
    6602: ResultInfo('Address not found.'),
    6603: ResultInfo('Address is out of resources.'),
    6700: ResultInfo('Virtual machine condition depth is invalid.')
}, {
    (6500, 6599): 'Cheat engine error.',
                  (6600, 6699): 'Frozen address error.'
})

pm = Module('pm', {
    1: ResultInfo('Process not found.'),
    2: ResultInfo('Already started.'),
    3: ResultInfo('Not terminated.'),
    4: ResultInfo('Debug hook in use.'),
    5: ResultInfo('Application running.'),
    6: ResultInfo('Invalid size.')
})

ns = Module('ns', {
    90: ResultInfo('Canceled.'),
    110: ResultInfo('Out of max running tasks.'),
    120: ResultInfo('System update is not required.'),
    251: ResultInfo('Unexpected storage ID.'),
    270: ResultInfo('Card update not set up.'),
    280: ResultInfo('Card update not prepared.'),
    290: ResultInfo('Card update already set up.'),
    340: ResultInfo('IsAnyInternetRequestAccepted with the output from GetClientId returned false.'),
    460: ResultInfo('PrepareCardUpdate already requested.'),
    801: ResultInfo('SystemDeliveryInfo system_delivery_protocol_version is less than the system setting.'),
    802: ResultInfo('SystemDeliveryInfo system_delivery_protocol_version is greater than the system setting.'),
    892: ResultInfo('Unknown state: reference count is zero.'),
    931: ResultInfo('Invalid SystemDeliveryInfo HMAC/invalid Meta ID.'),
    2101: ResultInfo('Inserted region-locked Tencent-Nintendo (Chinese) game cartridge into a non-Chinese console.',
                     'https://nintendoswitch.com.cn/support/')
})

kvdb = Module('kvdb', {
    1: ResultInfo('Out of key resources.'),
    2: ResultInfo('Key not found.'),
    4: ResultInfo('Allocation failed.'),
    5: ResultInfo('Invalid key value.'),
    6: ResultInfo('Buffer insufficient.'),
    8: ResultInfo('Invalid filesystem state.'),
    9: ResultInfo('Not created.')
})

sm = Module('sm', {
    1: ResultInfo('Out of processes.'),
    2: ResultInfo('Invalid client (not initialized).'),
    3: ResultInfo('Out of sessions.'),
    4: ResultInfo('Already registered.'),
    5: ResultInfo('Out of services.'),
    6: ResultInfo('Invalid service name.'),
    7: ResultInfo('Not registered.'),
    8: ResultInfo('Not allowed (permission denied).'),
    9: ResultInfo('Access control is too large.'),

    1000: ResultInfo('Should forward to session.'),
    1100: ResultInfo('Process is not associated.')
}, {
    (1000, 2000): 'Atmosphere man-in-the-middle (MITM) extension result.'
})

ro = Module('ro', {
    2: ResultInfo('Out of address space.'),
    3: ResultInfo('NRO already loaded.'),
    4: ResultInfo('Invalid NRO.'),
    6: ResultInfo('Invalid NRR.'),
    7: ResultInfo('Too many NROs.'),
    8: ResultInfo('Too many NRRs.'),
    9: ResultInfo('Not authorized (bad NRO hash or NRR signature).'),
    10: ResultInfo('Invalid NRR type.'),
    1023: ResultInfo('Internal error.'),
    1025: ResultInfo('Invalid address.'),
    1026: ResultInfo('Invalid size.'),
    1028: ResultInfo('NRO not loaded.'),
    1029: ResultInfo('NRO not registered.'),
    1030: ResultInfo('Invalid session (already initialized).'),
    1031: ResultInfo('Invalid process (not initialized).')
})

spl = Module('spl', {
    1: ResultInfo('Secure monitor: function is not implemented.'),
    2: ResultInfo('Secure monitor: invalid argument.'),
    3: ResultInfo('Secure monitor is busy.'),
    4: ResultInfo('Secure monitor: function is not an async operation.'),
    5: ResultInfo('Secure monitor: invalid async operation.'),
    6: ResultInfo('Secure monitor: not permitted.'),
    7: ResultInfo('Secure monitor: not initialized.'),
    100: ResultInfo('Invalid size.'),
    101: ResultInfo('Unknown secure monitor error.'),
    102: ResultInfo('Decryption failed.'),
    104: ResultInfo('Out of keyslots.'),
    105: ResultInfo('Invalid keyslot.'),
    106: ResultInfo('Boot reason was already set.'),
    107: ResultInfo('Boot reason was not set.'),
    108: ResultInfo('Invalid argument.')
}, {
    (0, 99): 'Secure monitor error.'
})

i2c = Module('i2c', {
    1: ResultInfo('No ACK.'),
    2: ResultInfo('Bus is busy.'),
    3: ResultInfo('Command list is full.'),
    4: ResultInfo('Timed out.'),
    5: ResultInfo('Unknown device.')
})

settings = Module('settings', {
    11: ResultInfo('Settings item not found.'),
    101: ResultInfo('Settings item key allocation failed.'),
    102: ResultInfo('Settings item value allocation failed.'),
    201: ResultInfo('Settings name is null.'),
    202: ResultInfo('Settings item key is null.'),
    203: ResultInfo('Settings item value is null.'),
    204: ResultInfo('Settings item key buffer is null.'),
    205: ResultInfo('Settings item value buffer is null.'),
    221: ResultInfo('Settings name is empty.'),
    222: ResultInfo('Settings item key is empty.'),
    241: ResultInfo('Settings group name is too long.'),
    242: ResultInfo('Settings item key is too long.'),
    261: ResultInfo('Settings group name has invalid format.'),
    262: ResultInfo('Settings item key has invalid format.'),
    263: ResultInfo('Settings item value has invalid format.'),
    621: ResultInfo('Language code.'),
    625: ResultInfo('Language out of range.'),
    631: ResultInfo('Network.'),
    651: ResultInfo('Bluetooth device.'),
    652: ResultInfo('Bluetooth device setting output count.'),
    653: ResultInfo('Bluetooth enable flag.'),
    654: ResultInfo('Bluetooth AFH enable flag.'),
    655: ResultInfo('Bluetooth boost enable flag.'),
    656: ResultInfo('BLE pairing.'),
    657: ResultInfo('BLE pairing settings entry count.'),
    661: ResultInfo('External steady clock source ID.'),
    662: ResultInfo('User system clock context.'),
    663: ResultInfo('Network system clock context.'),
    664: ResultInfo('User system clock automatic correction enabled flag.'),
    665: ResultInfo('Shutdown RTC value.'),
    666: ResultInfo('External steady clock internal offset.'),
    671: ResultInfo('Account settings.'),
    681: ResultInfo('Audio volume.'),
    683: ResultInfo('ForceMuteOnHeadphoneRemoved.'),
    684: ResultInfo('Headphone volume warning.'),
    687: ResultInfo('Invalid audio output mode.'),
    688: ResultInfo('Headphone volume update flag.'),
    691: ResultInfo('Console information upload flag.'),
    701: ResultInfo('Automatic application download flag.'),
    702: ResultInfo('Notification settings.'),
    703: ResultInfo('Account notification settings entry count.'),
    704: ResultInfo('Account notification settings.'),
    711: ResultInfo('Vibration master volume.'),
    712: ResultInfo('NX controller settings.'),
    713: ResultInfo('NX controller settings entry count.'),
    714: ResultInfo('USB full key enable flag.'),
    721: ResultInfo('TV settings.'),
    722: ResultInfo('EDID.'),
    731: ResultInfo('Data deletion settings.'),
    741: ResultInfo('Initial system applet program ID.'),
    742: ResultInfo('Overlay disp program ID.'),
    743: ResultInfo('IsInRepairProcess.'),
    744: ResultInfo('RequresRunRepairTimeReviser.'),
    751: ResultInfo('Device timezone location name.'),
    761: ResultInfo('Primary album storage.'),
    771: ResultInfo('USB 3.0 enable flag.'),
    772: ResultInfo('USB Type-C power source circuit version.'),
    781: ResultInfo('Battery lot.'),
    791: ResultInfo('Serial number.'),
    801: ResultInfo('Lock screen flag.'),
    803: ResultInfo('Color set ID.'),
    804: ResultInfo('Quest flag.'),
    805: ResultInfo('Wireless certification file size.'),
    806: ResultInfo('Wireless certification file.'),
    807: ResultInfo('Initial launch settings.'),
    808: ResultInfo('Device nickname.'),
    809: ResultInfo('Battery percentage flag.'),
    810: ResultInfo('Applet launch flags.'),
    1012: ResultInfo('Wireless LAN enable flag.'),
    1021: ResultInfo('Product model.'),
    1031: ResultInfo('NFC enable flag.'),
    1041: ResultInfo('ECI device certificate.'),
    1042: ResultInfo('E-Ticket device certificate.'),
    1051: ResultInfo('Sleep settings.'),
    1061: ResultInfo('EULA version.'),
    1062: ResultInfo('EULA version entry count.'),
    1071: ResultInfo('LDN channel.'),
    1081: ResultInfo('SSL key.'),
    1082: ResultInfo('SSL certificate.'),
    1091: ResultInfo('Telemetry flags.'),
    1101: ResultInfo('Gamecard key.'),
    1102: ResultInfo('Gamecard certificate.'),
    1111: ResultInfo('PTM battery lot.'),
    1112: ResultInfo('PTM fuel gauge parameter.'),
    1121: ResultInfo('ECI device key.'),
    1122: ResultInfo('E-Ticket device key.'),
    1131: ResultInfo('Speaker parameter.'),
    1141: ResultInfo('Firmware version.'),
    1142: ResultInfo('Firmware version digest.'),
    1143: ResultInfo('Rebootless system update version.'),
    1151: ResultInfo('Mii author ID.'),
    1161: ResultInfo('Fatal flags.'),
    1171: ResultInfo('Auto update enable flag.'),
    1181: ResultInfo('External RTC reset flag.'),
    1191: ResultInfo('Push notification activity mode.'),
    1201: ResultInfo('Service discovery control setting.'),
    1211: ResultInfo('Error report share permission.'),
    1221: ResultInfo('LCD vendor ID.'),
    1231: ResultInfo('SixAxis sensor acceleration bias.'),
    1232: ResultInfo('SixAxis sensor angular velocity bias.'),
    1233: ResultInfo('SixAxis sensor acceleration gain.'),
    1234: ResultInfo('SixAxis sensor angular velocity gain.'),
    1235: ResultInfo('SixAxis sensor angular velocity time bias.'),
    1236: ResultInfo('SixAxis sensor angular acceleration.'),
    1241: ResultInfo('Keyboard layout.'),
    1245: ResultInfo('Invalid keyboard layout.'),
    1251: ResultInfo('Web inspector flag.'),
    1252: ResultInfo('Allowed SSL hosts.'),
    1253: ResultInfo('Allowed SSL hosts entry count.'),
    1254: ResultInfo('FS mount point.'),
    1271: ResultInfo('Amiibo key.'),
    1272: ResultInfo('Amiibo ECQV certificate.'),
    1273: ResultInfo('Amiibo ECDSA certificate.'),
    1274: ResultInfo('Amiibo ECQV BLS key.'),
    1275: ResultInfo('Amiibo ECQV BLS certificate.'),
    1276: ResultInfo('Amiibo ECQV BLS root certificate.')
}, {
    (100, 149): 'Internal error.',
    (200, 399): 'Invalid argument.',
    (621, 1276): 'Setting buffer is null.',
})

nifm = Module(
    'nifm', {
        3400: ResultInfo(
            'The internet connection you are using requires authentication or a user agreement.'
            'https://en-americas-support.nintendo.com/app/answers/detail/a_id/22569/kw/2110-3400'), })

vi = Module('vi', {
    1: ResultInfo('Operation failed.'),
    6: ResultInfo('Not supported.'),
    7: ResultInfo('Not found.')
})

nfp = Module('nfp', {
    64: ResultInfo('Device not found.'),
    96: ResultInfo('Needs restart.'),
    128: ResultInfo('Area needs to be created.'),
    152: ResultInfo('Access ID mismatch.'),
    168: ResultInfo('Area already created.')
})

time = Module('time', {
    0: ResultInfo('Not initialized.'),
    1: ResultInfo('Permission denied.'),
    102: ResultInfo('Time not set (clock source ID mismatch).'),
    200: ResultInfo('Not comparable.'),
    201: ResultInfo('Signed over/under-flow.'),
    801: ResultInfo('Memory allocation failure.'),
    901: ResultInfo('Invalid pointer.'),
    902: ResultInfo('Value out of range.'),
    903: ResultInfo('TimeZoneRule conversion failed.'),
    989: ResultInfo('TimeZone location name not found.'),
    990: ResultInfo('Unimplemented.')
}, {
    (900, 919): 'Invalid argument.'
})

friends = Module('friends', {
    6: ResultInfo('IsAnyInternetRequestAccepted with the output from GetClientId returned false.'),
})

bcat = Module('bcat', {
    1: ResultInfo('Invalid argument.'),
    2: ResultInfo('Object not found.'),
    3: ResultInfo('Object locked (in use).'),
    4: ResultInfo('Target already mounted.'),
    5: ResultInfo('Target not mounted.'),
    6: ResultInfo('Object already opened.'),
    7: ResultInfo('Object not opened.'),
    8: ResultInfo('IsAnyInternetRequestAccepted with the output from GetClientId returned false.'),
    80: ResultInfo('Passphrase not found.'),
    81: ResultInfo('Data verification failed.'),
    90: ResultInfo('Invalid API call.'),
    98: ResultInfo('Invalid operation.')
})

ssl = Module('ssl', {
    11: ResultInfo('Returned during various NSS SEC, NSPR and NSS SSL errors.',
                   'https://switchbrew.org/wiki/Error_codes'),
    13: ResultInfo('Unrecognized error.'),
    102: ResultInfo('Out of memory or table full (NSS SEC error -8173 or NSPR errors -6000, -5974, -5971).'),
    116: ResultInfo('NSPR error -5999 (PR_BAD_DESCRIPTOR_ERROR).'),
    204: ResultInfo('NSPR error -5998 (PR_WOULD_BLOCK_ERROR).'),
    205: ResultInfo('NSPR error -5990 (PR_IO_TIMEOUT_ERROR).'),
    206: ResultInfo('NSPR error -5935 (PR_OPERATION_ABORTED_ERROR)..'),
    208: ResultInfo('NSPR error -5978 (PR_NOT_CONNECTED_ERROR).'),
    209: ResultInfo('NSPR error -5961 (PR_CONNECT_RESET_ERROR).'),
    210: ResultInfo('NSPR error -5928 (PR_CONNECT_ABORTED_ERROR).'),
    211: ResultInfo('NSPR error -5929 (PR_SOCKET_SHUTDOWN_ERROR).'),
    212: ResultInfo('NSPR error -5930 (PR_NETWORK_DOWN_ERROR).'),
    215: ResultInfo('ClientPki/InternalPki was already previously imported/registered.'),
    218: ResultInfo('Maximum number of ServerPki objects were already imported.'),
    301: ResultInfo('NSS SSL error -12276 (SSL_ERROR_BAD_CERT_DOMAIN).'),
    302: ResultInfo('NSS SSL error -12285 (SSL_ERROR_NO_CERTIFICATE).'),
    303: ResultInfo(
        'NSS SEC errors: -8181 (SEC_ERROR_EXPIRED_CERTIFICATE), -8162 (SEC_ERROR_EXPIRED_ISSUER_CERTIFICATE).'),
    304: ResultInfo('NSS SEC error -8180 (SEC_ERROR_REVOKED_CERTIFICATE).'),
    305: ResultInfo('NSS SEC error -8183 (SEC_ERROR_BAD_DER).'),
    306: ResultInfo('NSS SEC errors: -8102 (SEC_ERROR_INADEQUATE_KEY_USAGE), -8101 (SEC_ERROR_INADEQUATE_CERT_TYPE).'),
    307: ResultInfo(
        'NSS SEC errors: -8185 (SEC_ERROR_INVALID_AVA), -8182 (SEC_ERROR_BAD_SIGNATURE), -8158 (SEC_ERROR_EXTENSION_VALUE_INVALID), -8156 (SEC_ERROR_CA_CERT_INVALID), -8151 (SEC_ERROR_UNKNOWN_CRITICAL_EXTENSION), -8080 (SEC_ERROR_CERT_NOT_IN_NAME_SPACE).'),
    308: ResultInfo(
        'NSS SEC errors: -8179 (SEC_ERROR_UNKNOWN_ISSUER), -8172 (SEC_ERROR_UNTRUSTED_ISSUER), -8014 (SEC_ERROR_APPLICATION_CALLBACK_ERROR).'),
    309: ResultInfo('NSS SEC error -8171 (SEC_ERROR_UNTRUSTED_CERT).'),
    310: ResultInfo(
        'NSS SSL errors: -12233 (SSL_ERROR_RX_UNKNOWN_RECORD_TYPE), -12232 (SSL_ERROR_RX_UNKNOWN_HANDSHAKE), -12231 (SSL_ERROR_RX_UNKNOWN_ALERT). This is also returned by ImportClientPki when import fails.'),
    311: ResultInfo('NSS SSL errors: One of various malformed request errors. See Switchbrew for the complete list.'),
    312: ResultInfo('NSS SEC errors: One of various unexpected request errors. See Switchbrew for the complete list.'),
    313: ResultInfo(
        ' NSS SSL errors: -12237 (SSL_ERROR_RX_UNEXPECTED_CHANGE_CIPHER), -12236 (SSL_ERROR_RX_UNEXPECTED_ALERT), -12235 (SSL_ERROR_RX_UNEXPECTED_HANDSHAKE), -12234 (SSL_ERROR_RX_UNEXPECTED_APPLICATION_DATA).'),
    314: ResultInfo('NSS SSL error -12263 (SSL_ERROR_RX_RECORD_TOO_LONG).'),
    315: ResultInfo('NSS SSL error -12165 (SSL_ERROR_RX_UNEXPECTED_HELLO_VERIFY_REQUEST).'),
    316: ResultInfo('NSS SSL error -12163 (SSL_ERROR_RX_UNEXPECTED_CERT_STATUS).'),
    317: ResultInfo('NSS SSL error -12160 (SSL_ERROR_INCORRECT_SIGNATURE_ALGORITHM).'),
    318: ResultInfo(
        'NSS SSL errors: -12173 (SSL_ERROR_WEAK_SERVER_EPHEMERAL_DH_KEY), -12156 (SSL_ERROR_WEAK_SERVER_CERT_KEY).'),
    319: ResultInfo('NSS SSL error -12273 (SSL_ERROR_BAD_MAC_READ).'),
    321: ResultInfo(
        'NSS SSL errors: -12215 (SSL_ERROR_MD5_DIGEST_FAILURE), -12214 (SSL_ERROR_SHA_DIGEST_FAILURE), -12161 (SSL_ERROR_DIGEST_FAILURE).'),
    322: ResultInfo('NSS SSL error -12213 (SSL_ERROR_MAC_COMPUTATION_FAILURE).'),
    324: ResultInfo('NSS SEC error -8157 (SEC_ERROR_EXTENSION_NOT_FOUND).'),
    325: ResultInfo('NSS SEC error -8049 (SEC_ERROR_UNRECOGNIZED_OID).'),
    326: ResultInfo('NSS SEC error -8032 (SEC_ERROR_POLICY_VALIDATION_FAILED).'),
    330: ResultInfo('NSS SSL error -12177 (SSL_ERROR_DECOMPRESSION_FAILURE).'),
    1501: ResultInfo('NSS SSL error -12230 (SSL_ERROR_CLOSE_NOTIFY_ALERT).'),
    1502: ResultInfo('NSS SSL error -12229 (SSL_ERROR_HANDSHAKE_UNEXPECTED_ALERT).'),
    1503: ResultInfo('NSS SSL error -12272 (SSL_ERROR_BAD_MAC_ALERT).'),
    1504: ResultInfo('NSS SSL error -12197 (SSL_ERROR_DECRYPTION_FAILED_ALERT).'),
    1505: ResultInfo('NSS SSL error -12196 (SSL_ERROR_RECORD_OVERFLOW_ALERT).'),
    1506: ResultInfo('NSS SSL error -12228 (SSL_ERROR_DECOMPRESSION_FAILURE_ALERT).'),
    1507: ResultInfo('NSS SSL error -12227 (SSL_ERROR_HANDSHAKE_FAILURE_ALERT).'),
    1509: ResultInfo('NSS SSL error -12271 (SSL_ERROR_BAD_CERT_ALERT).'),
    1510: ResultInfo('NSS SSL error -12225 (SSL_ERROR_UNSUPPORTED_CERT_ALERT).'),
    1511: ResultInfo('NSS SSL error -12270 (SSL_ERROR_REVOKED_CERT_ALERT).'),
    1512: ResultInfo('NSS SSL error -12269 (SSL_ERROR_EXPIRED_CERT_ALERT).'),
    1513: ResultInfo('NSS SSL error -12224 (SSL_ERROR_CERTIFICATE_UNKNOWN_ALERT).'),
    1514: ResultInfo('NSS SSL error -12226 (SSL_ERROR_ILLEGAL_PARAMETER_ALERT).'),
    1515: ResultInfo('NSS SSL error -12195 (SSL_ERROR_UNKNOWN_CA_ALERT).'),
    1516: ResultInfo('NSS SSL error -12194 (SSL_ERROR_ACCESS_DENIED_ALERT).'),
    1517: ResultInfo('NSS SSL error -12193 (SSL_ERROR_DECODE_ERROR_ALERT).'),
    1518: ResultInfo('NSS SSL error -12192 (SSL_ERROR_DECRYPT_ERROR_ALERT).'),
    1519: ResultInfo('NSS SSL error -12191 (SSL_ERROR_EXPORT_RESTRICTION_ALERT).'),
    1520: ResultInfo('NSS SSL error -12190 (SSL_ERROR_PROTOCOL_VERSION_ALERT).'),
    1521: ResultInfo('NSS SSL error -12189 (SSL_ERROR_INSUFFICIENT_SECURITY_ALERT).'),
    1522: ResultInfo('NSS SSL error -12188 (SSL_ERROR_INTERNAL_ERROR_ALERT).'),
    1523: ResultInfo('NSS SSL error -12157 (SSL_ERROR_INAPPROPRIATE_FALLBACK_ALERT).'),
    1524: ResultInfo('NSS SSL error -12187 (SSL_ERROR_USER_CANCELED_ALERT).'),
    1525: ResultInfo('NSS SSL error -12186 (SSL_ERROR_NO_RENEGOTIATION_ALERT).'),
    1526: ResultInfo('NSS SSL error -12184 (SSL_ERROR_UNSUPPORTED_EXTENSION_ALERT).'),
    1527: ResultInfo('NSS SSL error -12183 (SSL_ERROR_CERTIFICATE_UNOBTAINABLE_ALERT).'),
    1528: ResultInfo('NSS SSL error -12182 (SSL_ERROR_UNRECOGNIZED_NAME_ALERT).'),
    1529: ResultInfo('NSS SSL error -12181 (SSL_ERROR_BAD_CERT_STATUS_RESPONSE_ALERT).'),
    1530: ResultInfo('NSS SSL error -12180 (SSL_ERROR_BAD_CERT_HASH_VALUE_ALERT).'),
    5001: ResultInfo('NSS SSL error -12155 (SSL_ERROR_RX_SHORT_DTLS_READ).'),
    5007: ResultInfo('Out-of-bounds error during error conversion.')
})

account = Module(
    'account',
    {
        59: ResultInfo('IsAnyInternetRequestAccepted with the output from GetClientId returned false.'),
        3000: ResultInfo(
            'System update is required.',
            'https://en-americas-support.nintendo.com/app/answers/detail/a_id/27166/'),
        4007: ResultInfo(
            'Console is permanently banned.',
            'https://en-americas-support.nintendo.com/app/answers/detail/a_id/28046/',
            is_ban=True),
        4025: ResultInfo(
            'Game Card is banned. If you have a legitimate cartridge and this happened to you, contact Nintendo.',
            is_ban=True),
        4027: ResultInfo(
            'Console (and Nintendo Account) are temporarily banned from a game.',
            is_ban=True),
        4508: ResultInfo(
            'Console is permanently banned.',
            'https://en-americas-support.nintendo.com/app/answers/detail/a_id/28046/',
            is_ban=True),
        4517: ResultInfo(
            'Console is permanently banned.',
            'https://en-americas-support.nintendo.com/app/answers/detail/a_id/43652/',
            is_ban=True),
        4609: ResultInfo(
            'The online service is no longer available.',
            'https://en-americas-support.nintendo.com/app/answers/detail/a_id/46482/'),
        4621: ResultInfo(
            'Tencent-Nintendo (Chinese) consoles cannot use online features in foreign games.'
            'https://nintendoswitch.com.cn/support/'),
        5111: ResultInfo(
            'Complete account ban.',
            is_ban=True)})

mii = Module('mii', {
    1: ResultInfo('Invalid argument.'),
    4: ResultInfo('Entry not found.'),
    67: ResultInfo('Invalid database signature value (should be "NFDB").'),
    69: ResultInfo('Invalid database entry count.'),
    204: ResultInfo('Development/debug-only behavior.')
})

am = Module('am', {
    2: ResultInfo('IStorage not available.'),
    3: ResultInfo('No messages.'),
    35: ResultInfo('Error while launching applet.'),
    37: ResultInfo('Program ID not found. This usually happens when applet launch fails.'),
    500: ResultInfo('Invalid input.'),
    502: ResultInfo('IStorage is already opened.'),
    503: ResultInfo('IStorage read/write out of bounds.'),
    506: ResultInfo('Invalid parameters.'),
    511: ResultInfo(
        'IStorage opened as wrong type (e.g. data opened as TransferMemory, or TransferMemory opened as data.'),
    518: ResultInfo('Null object.'),
    600: ResultInfo('Failed to allocate memory for IStorage.'),
    712: ResultInfo('Thread stack pool exhausted.'),
    974: ResultInfo('DebugMode not enabled.'),
    980: ResultInfo('am.debug!dev_function setting needs to be set (DebugMode not enabled).'),
    998: ResultInfo('Not implemented.'),
})

prepo = Module('prepo', {
    102: ResultInfo('Transmission not agreed.'),
    105: ResultInfo('Network unavailable.'),
    1005: ResultInfo('Couldn\'t resolve proxy.'),
    1006: ResultInfo('Couldn\'t resolve host.'),
    1007: ResultInfo('Couldn\'t connect.'),
    1023: ResultInfo('Write error.'),
    1026: ResultInfo('Read error.'),
    1027: ResultInfo('Out of memory.'),
    1028: ResultInfo('Operation timed out.'),
    1035: ResultInfo('SSL connection error.'),
    1051: ResultInfo('Peer failed verification.'),
    1052: ResultInfo('Got nothing.'),
    1055: ResultInfo('Send error.'),
    1056: ResultInfo('Recv error.'),
    1058: ResultInfo('SSL cert problem.'),
    1059: ResultInfo('SSL cipher.'),
    1060: ResultInfo('SSL CA cert.'),
    2400: ResultInfo('Status 400.'),
    2401: ResultInfo('Status 401.'),
    2403: ResultInfo('Status 403.'),
    2500: ResultInfo('Status 500.'),
    2503: ResultInfo('Status 503.'),
    2504: ResultInfo('Status 504.'),
}, {
    (1005, 1060): 'HTTP error.',
    (2400, 2504): 'Server error.'
})

pcv = Module('pcv', {
    2: ResultInfo('Invalid DVFS table ID.'),
    3: ResultInfo('DVFS table ID for debug only.'),
    4: ResultInfo('Invalid parameter.')
})

nim = Module('nim', {
    10: ResultInfo('Already initialized.'),
    30: ResultInfo('Task not found.'),
    40: ResultInfo('Memory allocation failed (due to bad input?).'),
    70: ResultInfo('HTTP connection canceled.'),
    330: ResultInfo('ContentMetaType does not match SystemUpdate.'),
    5001: ResultInfo(
        'A socket error occurred (ENETDOWN, ECONNRESET, EHOSTDOWN, EHOSTUNREACH, or EPIPE). Also occurs when the received size doesn\'t match the expected size (recvfrom() ret with meta_size data receiving).'),
    5010: ResultInfo('Socket was shutdown due to the async operation being cancelled.'),
    5020: ResultInfo('Too many internal input entries with nim command 42, or an unrecognized socket error occurred.'),
    5100: ResultInfo('Connection time-out.'),
    5410: ResultInfo('Invalid ID.'),
    5420: ResultInfo(
        'Invalid magicnum. Can also be caused by the connection being closed by the peer, since non-negative return values from recv() are ignored in this case.'),
    5430: ResultInfo('Invalid data_size.'),
    5440: ResultInfo('The input ContentMetaKey doesn\'t match the ContentMetaKey in state.'),
    5450: ResultInfo('Invalid meta_size.'),
    7001: ResultInfo('Invalid HTTP response code (>=600).'),
    7002: ResultInfo('Invalid HTTP client response code (4xx).'),
    7003: ResultInfo('Invalid HTTP server response code (5xx).'),
    7004: ResultInfo('Invalid HTTP redirect response code (3xx).'),
    (7300, 7308): ResultInfo('HTTP response code 300-308.'),
    (7400, 7417): ResultInfo('HTTP response code 400-417.'),
    (7500, 7509): ResultInfo('HTTP response code 500-509.'),
    7800: ResultInfo('Unknown/invalid libcurl error.'),
    (8001, 8096): ResultInfo('libcurl error 1-96. Some errors map to the 7800 result code range instead, however.')
})

psc = Module('psc', {
    2: ResultInfo('Already initialized.'),
    3: ResultInfo('Not initialized.')
})

usb = Module('usb', {
    51: ResultInfo('USB data transfer in progress.'),
    106: ResultInfo('Invalid descriptor.'),
    201: ResultInfo('USB device not bound or interface already enabled.')
})

pctl = Module('pctl', {
    223: ResultInfo('IsAnyInternetRequestAccepted with the output from GetClientId returned false.')
})

applet = Module('applet', {
    1: ResultInfo('Exited abnormally.'),
    3: ResultInfo('Cancelled.'),
    4: ResultInfo('Rejected.'),
    5: ResultInfo('Exited unexpectedly.')
})

erpt = Module('erpt', {
    1: ResultInfo('Not initialized.'),
    2: ResultInfo('Already initialized.'),
    3: ResultInfo('Out of array space.'),
    4: ResultInfo('Out of field space.'),
    5: ResultInfo('Out of memory.'),
    7: ResultInfo('Invalid argument.'),
    8: ResultInfo('Not found.'),
    9: ResultInfo('Field category mismatch.'),
    10: ResultInfo('Field type mismatch.'),
    11: ResultInfo('Already exists.'),
    12: ResultInfo('Journal is corrupted.'),
    13: ResultInfo('Category not found.'),
    14: ResultInfo('Required context is missing.'),
    15: ResultInfo('Required field is missing.'),
    16: ResultInfo('Formatter error.'),
    17: ResultInfo('Invalid power state.'),
    18: ResultInfo('Array field is too large.'),
    19: ResultInfo('Already owned.')
})

audio = Module('audio', {
    1: ResultInfo('Invalid audio device.'),
    2: ResultInfo('Operation failed.'),
    3: ResultInfo('Invalid sample rate.'),
    4: ResultInfo('Buffer size too small.'),
    8: ResultInfo('Too many buffers are still unreleased.'),
    10: ResultInfo('Invalid channel count.'),
    513: ResultInfo('Invalid/unsupported operation.'),
    1536: ResultInfo('Invalid handle.'),
    1540: ResultInfo('Audio output was already started.')
})

arp = Module('arp', {
    30: ResultInfo('Address is NULL.'),
    31: ResultInfo('PID is NULL.'),
    42: ResultInfo('Already bound'),
    102: ResultInfo('Invalid PID.')
})

updater = Module('updater', {
    2: ResultInfo('Boot image package not found.'),
    3: ResultInfo('Invalid boot image package.'),
    4: ResultInfo('Work buffer is too small.'),
    5: ResultInfo('Work buffer is not aligned.'),
    6: ResultInfo('Needs repair boot images.')
})

userland_assert = Module('userland (assert)', {
    0: ResultInfo('Undefined instruction.'),
    1: ResultInfo('Application aborted (usually svcBreak).'),
    2: ResultInfo('System module aborted.'),
    3: ResultInfo('Unaligned userland PC.'),
    8: ResultInfo('Attempted to call an SVC outside of the whitelist.')
})

fatal = Module('fatal', {
    1: ResultInfo('Allocation failed.'),
    2: ResultInfo('Graphics buffer is null.'),
    3: ResultInfo('Already thrown.'),
    4: ResultInfo('Too many events.'),
    5: ResultInfo('In repair without volume held.'),
    6: ResultInfo('In repair without time reviser cartridge.')
})

ec = Module('ec', {
    20: ResultInfo('Unable to start the software.',
                   'https://en-americas-support.nintendo.com/app/answers/detail/a_id/22539/kw/2164-0020'),
    56: ResultInfo('IsAnyInternetRequestAccepted with the output from GetClientId returned false.')
})

creport = Module('userland assert/crash', {
    0: ResultInfo('Undefined instruction.'),
    1: ResultInfo('Instruction abort.'),
    2: ResultInfo('Data abort.'),
    3: ResultInfo('Alignment fault.'),
    4: ResultInfo('Debugger attached.'),
    5: ResultInfo('Breakpoint.'),
    6: ResultInfo('User break.'),
    7: ResultInfo('Debugger break.'),
    8: ResultInfo('Undefined system call.'),
    9: ResultInfo('Memory system error.'),
    99: ResultInfo('Report is incomplete.')
})

jit = Module('jit', {
    2: ResultInfo('Bad version.'),
    101: ResultInfo('Input NRO/NRR is too large for the storage buffer.'),
    600: ResultInfo('Function pointer is not initialized (Control/GenerateCode).'),
    601: ResultInfo('DllPlugin not initialized, or plugin NRO already loaded.'),
    602: ResultInfo('An error occurred when calling the function pointer with the Control command.'),
})

dauth = Module('dauth', {
    4008: ResultInfo('Console is permanently banned by Nintendo.',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/42061/kw/2181-4008', is_ban=True)
})

dbg = Module('dbg', {
    1: ResultInfo('Cannot debug.'),
    2: ResultInfo('Already attached.'),
    3: ResultInfo('Cancelled.')
})

calibration = Module('calibration', {
    101: ResultInfo('Calibration data CRC error.'),
})

capsrv = Module('capsrv (capture)', {
    3: ResultInfo('Album work memory error.'),
    7: ResultInfo('Album is already opened.'),
    8: ResultInfo('Album is out of range.'),
    11: ResultInfo('The application ID is invalid.'),
    12: ResultInfo('The timestamp is invalid.'),
    13: ResultInfo('The storage is invalid.'),
    14: ResultInfo('The filecontents is invalid.'),
    21: ResultInfo('Album is not mounted.'),
    22: ResultInfo('Album is full.'),
    23: ResultInfo('File not found.'),
    24: ResultInfo('The file data is invalid.'),
    25: ResultInfo('The file count limit has been reached.'),
    26: ResultInfo('The file has no thumbnail.'),
    30: ResultInfo('The read buffer is too small.'),
    96: ResultInfo('The destination is corrupted.'),
    820: ResultInfo('Control resource limit reached.'),
    822: ResultInfo('Control is not opened.'),
    1023: ResultInfo('Not supported.'),
    1210: ResultInfo('Internal JPEG encoder error.'),
    1212: ResultInfo('Internal JPEG work memory shortage.'),
    1301: ResultInfo('The file data was empty.'),
    1302: ResultInfo('EXIF extraction failed.'),
    1303: ResultInfo('EXIF data analysis failed.'),
    1304: ResultInfo('Datetime extraction failed.'),
    1305: ResultInfo('Invalid datetime length.'),
    1306: ResultInfo('Inconsistent datatime.'),
    1307: ResultInfo('Make note extraction failed.'),
    1308: ResultInfo('Inconsistent application ID.'),
    1309: ResultInfo('Inconsistent signature.'),
    1310: ResultInfo('Unsupported orientation.'),
    1311: ResultInfo('Invalid data dimension.'),
    1312: ResultInfo('Inconsistent orientation.'),
    1401: ResultInfo('File count limit has been reached.'),
    1501: ResultInfo('EXIF extraction failed.'),
    1502: ResultInfo('Maker note extraction failed'),
    1701: ResultInfo('Album session limit reached.'),
    1901: ResultInfo('File count limit reached.'),
    1902: ResultInfo('Error when creating file.'),
    1903: ResultInfo('File creation retry limit reached.'),
    1904: ResultInfo('Error opening file.'),
    1905: ResultInfo('Error retrieving the file size.'),
    1906: ResultInfo('Error setting the file size.'),
    1907: ResultInfo('Error when reading the file.'),
    1908: ResultInfo('Error when writing the file.')
}, {
    (10, 19): 'Album: invalid file ID.',
    (90, 99): 'Album: filesystem error.',
    (800, 899): 'Control error.',
    # (1024, 2047): 'Internal error.',
    (1200, 1299): 'Internal JPEG encoder error.',
    (1300, 1399): 'Internal file data verification error.',
    (1400, 1499): 'Internal album limitation error.',
    (1500, 1599): 'Internal signature error.',
    (1700, 1799): 'Internal album session error.',
    (1900, 1999): 'Internal album temporary file error.'

})

pgl = Module('pgl', {
    2: ResultInfo('Not available.'),
    3: ResultInfo('Application not running.'),
    4: ResultInfo('Buffer is not enough.'),
    5: ResultInfo('Application content record was not found.'),
    6: ResultInfo('Content meta was not found.')
})

web_applet = Module('web applet', {
    1006: ResultInfo('This error code indicates an issue with the DNS used or that the connection timed out.',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/25859/p/897'),
    1028: ResultInfo('This error code generally indicates that your connection to the Nintendo eShop has timed out.',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/22503/p/897'),
    2750: ResultInfo('MP4 parsing failed.'),
    5001: ResultInfo(
        'This error code indicates an error occurred when connecting to the service, likely the result of the network environment.',
        'https://en-americas-support.nintendo.com/app/answers/detail/a_id/22392/p/897'),
})

youtube_app = Module('youtube', {
    0: ResultInfo(
        'This error typically occurs when your system clock isn\'t set correctly. If the problem persists, try reinstalling YouTube from the Nintendo eShop.')
})

arms_game = Module('ARMS', {
    1021: ResultInfo('This error code indicates the connection has likely timed out during a download.',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/26250/~/error-code%3A-2-aabqa-1021')
})

splatoon_game = Module('Splatoon 2', {
    3400: ResultInfo('You have been kicked from the online service due to using exefs/romfs edits.')
})

# known homebrew modules go below here
libnx = Module('libnx', {
    1: ResultInfo('Bad relocation.'),
    2: ResultInfo('Out of memory.'),
    3: ResultInfo('Already mapped.'),
    4: ResultInfo('Bad getinfo: stack.'),
    5: ResultInfo('Bad getinfo: heap.'),
    6: ResultInfo('Bad QueryMemory.'),
    7: ResultInfo('Aleady initialized.'),
    8: ResultInfo('Not initialized.'),
    9: ResultInfo('Not found.'),
    10: ResultInfo('I/O error.'),
    11: ResultInfo('Bad input.'),
    12: ResultInfo('Bad re-entry.'),
    13: ResultInfo('Buffer producer error.'),
    14: ResultInfo('Handle too early.'),
    15: ResultInfo('Heap alloc too early.'),
    16: ResultInfo('Heap alloc failed.'),
    17: ResultInfo('Too many overrides.'),
    18: ResultInfo('Parcel error.'),
    19: ResultInfo('Bad graphics init.'),
    20: ResultInfo('Bad graphics queue buffer.'),
    21: ResultInfo('Bad graphics dequeue buffer.'),
    22: ResultInfo('Applet command ID not found.'),
    23: ResultInfo('Bad applet receive message.'),
    24: ResultInfo('Bad applet notify running.'),
    25: ResultInfo('Bad applet get current focus state.'),
    26: ResultInfo('Bad applet get operation mode.'),
    27: ResultInfo('Bad applet get performance mode.'),
    28: ResultInfo('Bad USB comms read.'),
    29: ResultInfo('Bad USB comms write.'),
    30: ResultInfo('Failed to initialize sm.'),
    31: ResultInfo('Failed to initialize am.'),
    32: ResultInfo('Failed to initialize hid.'),
    33: ResultInfo('Failed to initialize fs.'),
    34: ResultInfo('Bad getinfo: rng'),
    35: ResultInfo('JIT unavailable.'),
    36: ResultInfo('Weird kernel.'),
    37: ResultInfo('Incompatible system firmware version.'),
    38: ResultInfo('Failed to initialize time.'),
    39: ResultInfo('Too many dev op tabs.'),
    40: ResultInfo('Domain message was of an unknown type.'),
    41: ResultInfo('Domain message had too many object IDs.'),
    42: ResultInfo('Failed to initialize applet.'),
    43: ResultInfo('Failed to initialize apm.'),
    44: ResultInfo('Failed to initialize nvinfo.'),
    45: ResultInfo('Failed to initialize nvbuf.'),
    46: ResultInfo('Libapplet bad exit.'),
    47: ResultInfo('Invalid CMIF out header.'),
    48: ResultInfo('Should not happen.')
})

hb_abi = Module('homebrew ABI', {
    0: ResultInfo('End of list.'),
    1: ResultInfo('Main thread handle.'),
    2: ResultInfo('Next load path.'),
    3: ResultInfo('Override heap.'),
    4: ResultInfo('Override service.'),
    5: ResultInfo('Argv.'),
    6: ResultInfo('Syscall available hint.'),
    7: ResultInfo('Applet type.'),
    8: ResultInfo('Applet workaround.'),
    9: ResultInfo('Reserved9.'),
    10: ResultInfo('Process handle.'),
    11: ResultInfo('Last load result.'),
    12: ResultInfo('Alloc pages.'),
    13: ResultInfo('Lock region.'),
    14: ResultInfo('Random seed.'),
    15: ResultInfo('User ID storage.'),
    16: ResultInfo('HOS version.')
})

hbl = Module('homebrew loader', {
    1: ResultInfo('Failed to initialize sm.'),
    2: ResultInfo('Failed to initialize fs.'),
    3: ResultInfo(
        'Next NRO to run was not found. This is usually caused by `hbmenu.nro` not being found on the root of the SD card.'),
    4: ResultInfo('Failed to read NRO.'),
    5: ResultInfo('NRO header magic is invalid.'),
    6: ResultInfo('NRO size does not match size indicated by header.'),
    7: ResultInfo('Failed to read the rest of the NRO.'),
    8: ResultInfo(
        'Reached an unreachable location in hbloader main(). What are you doing here? This area is off-limits.'),
    9: ResultInfo('Unable to set heap size, or heap address was NULL.'),
    10: ResultInfo('Failed to create service thread.'),
    12: ResultInfo('Unable to create svc session.'),
    13: ResultInfo('Failed to start service thread.'),
    15: ResultInfo('An error occurred while executing svcReplyAndReceive.'),
    17: ResultInfo('Too many (> 1) copy handles from hipcParseRequest.'),
    18: ResultInfo('Failed to map process code memory.'),
    19: ResultInfo('Failed to set process .text memory permissions.'),
    20: ResultInfo('Failed to set process .rodata memory permissions.'),
    21: ResultInfo('Failed to set process .data & .bss memory permissions.'),
    24: ResultInfo('Failed to unmap process .text.'),
    25: ResultInfo('Failed to unmap process .rodata.'),
    26: ResultInfo('Failed to unmap process .data and .bss.'),
    39: ResultInfo('Attempted to call exit(), which should never happen.'),
    404: ResultInfo('Failed to mount SD card.')
})

lnx_nvidia = Module('libnx (NVIDIA)', {
    1: ResultInfo('Not implemented.'),
    2: ResultInfo('Not supported.'),
    3: ResultInfo('Not initialized.'),
    4: ResultInfo('Bad parameter.'),
    5: ResultInfo('Timed out.'),
    6: ResultInfo('Insufficient memory.'),
    7: ResultInfo('Read-only attribute.'),
    8: ResultInfo('Invalid state.'),
    9: ResultInfo('Invalid address.'),
    10: ResultInfo('Invalid size.'),
    11: ResultInfo('Bad value.'),
    13: ResultInfo('Already allocated.'),
    14: ResultInfo('Busy.'),
    15: ResultInfo('Resource error.'),
    16: ResultInfo('Count mismatch.'),
    4096: ResultInfo('Shared memory too small.'),
    # 0x30003: ResultInfo('File operation failed.') # This actually belongs to OS.
})

lnx_binder = Module('libnx (binder)', {
    1: ResultInfo('Permission denied.'),
    2: ResultInfo('Name not found.'),
    11: ResultInfo('Would block.'),
    12: ResultInfo('No memory.'),
    17: ResultInfo('Already exists.'),
    19: ResultInfo('No init.'),
    22: ResultInfo('Bad value.'),
    32: ResultInfo('Dead object.'),
    38: ResultInfo('Invalid operation.'),
    61: ResultInfo('Not enough data.'),
    74: ResultInfo('Unknown transaction.'),
    75: ResultInfo('Bad index.'),
    110: ResultInfo('Timed out.')
    # TODO: How do I express INT32_MIN in pythonic terms?
    # -(INT32_MIN + 7): ResultInfo('Fds not allowed.'),
    # -(INT32_MIN + 2): ResultInfo('Failed transaction.'),
    # -(INT32_MIN + 1): ResultInfo('Bad type.'),
})

emuiibo = Module('emuiibo', {
    1: ResultInfo('No active virtual Amiibo.'),
    2: ResultInfo('Invalid virtual Amiibo.'),
    3: ResultInfo('Iterator end reached.'),
    4: ResultInfo('Unable to read Mii.')
})

exosphere = Module('exosphere', {
    1: ResultInfo('Not present.'),
    2: ResultInfo('Version mismatch.')
})

# We have some modules partially documented, those that aren't have dummy Modules.
modules = {
    1: kernel,
    2: fs,
    3: os,
    4: Module('htcs'),
    5: ncm,
    6: Module('dd'),
    7: dmnt,
    8: lr,
    9: loader,
    10: sf,
    11: hipc,
    13: dmnt,
    15: pm,
    16: ns,
    17: Module('bsdsockets'),
    18: Module('htc'),
    19: Module('tsc'),
    20: kvdb,
    21: sm,
    22: ro,
    23: Module('gc'),
    24: Module('sdmmc'),
    25: Module('ovln'),
    26: spl,
    27: Module('socket'),
    29: Module('htclow'),
    30: Module('bus'),
    31: Module('hfcsfs'),
    32: Module('async'),
    100: Module('ethc'),
    101: i2c,
    102: Module('gpio'),
    103: Module('uart'),
    105: settings,
    107: Module('wlan'),
    108: Module('xcd'),
    110: nifm,
    111: Module('hwopus'),
    113: Module('bluetooth'),
    114: vi,
    115: nfp,
    116: time,
    117: Module('fgm'),
    118: Module('oe'),
    120: Module('pcie'),
    121: friends,
    122: bcat,
    123: ssl,
    124: account,
    125: Module('news'),
    126: mii,
    127: Module('nfc'),
    128: am,
    129: prepo,
    130: Module('ahid'),
    132: Module('qlaunch'),
    133: pcv,
    134: Module('omm'),
    135: Module('bpc'),
    136: Module('psm'),
    137: nim,
    138: psc,
    139: Module('tc'),
    140: usb,
    141: Module('nsd'),
    142: pctl,
    143: Module('btm'),
    144: applet,
    145: Module('es'),
    146: Module('ngc'),
    147: erpt,
    148: Module('apm'),
    149: Module('cec'),
    150: Module('profiler'),
    151: Module('eupld'),
    153: audio,
    154: Module('npns'),
    155: Module('npns xmpp stream'),
    157: arp,
    158: updater,
    159: Module('swkbd'),
    161: Module('mifare'),
    162: userland_assert,
    163: fatal,
    164: ec,
    165: Module('spsm'),
    167: Module('bgtc'),
    168: creport,
    175: jit,
    178: Module('pdm'),
    179: Module('olsc'),
    180: Module('srepo'),
    181: dauth,
    183: dbg,
    187: Module('sasbus'),
    189: Module('pwm'),
    191: Module('rtc'),
    192: Module('regulator'),
    193: Module('led'),
    197: Module('clkrst'),
    198: calibration,
    202: Module('hid'),
    203: Module('ldn'),
    205: Module('irsensor'),
    206: capsrv,
    208: Module('manu'),
    210: Module('web'),
    211: Module('lcs'),
    212: Module('grc'),
    214: Module('album'),
    216: Module('migration'),
    218: Module('hidbus'),
    223: Module('websocket'),
    228: pgl,
    229: Module('notification'),
    230: Module('ins'),
    231: Module('lp2p'),

    800: web_applet,
    809: web_applet,
    810: web_applet,
    811: web_applet,
    'arvha': youtube_app,
    'aabqa': arms_game,
    'aab6a': splatoon_game,

    # Add non-nintendo modules below here.
    345: libnx,
    346: hb_abi,
    347: hbl,
    348: lnx_nvidia,
    349: lnx_binder,
    352: emuiibo,
    416: Module('SwitchPresence-Rewritten'),
    444: exosphere,
    789: Module('SwitchPresence-Old-Random'),
}

# regex for result code format "XXXX-YYYY"
RE = re.compile(r'2\d{3}-\d{4}')

# regex for result code format "2-BBBBB-CCCC"
# The first digit always appears to be "2" for games/applications.
RE_APP = re.compile(r'2-[a-zA-Z0-9]{5}-\d{4}')

CONSOLE_NAME = 'Nintendo Switch'

# Suggested color to use if displaying information through a Discord bot's embed
COLOR = 0xE60012


def is_valid(error):
    try:
        return int(error, 16) >= 0
    except ValueError:
        pass
    return RE.match(error) or RE_APP.match(error)


def err2hex(error, suppress_error=False):
    if RE.match(error):
        module = int(error[:4]) - 2000
        desc = int(error[5:9])
        code = (desc << 9) + module
        return hex(code)
    if RE_APP.match(error) and not suppress_error:
        return '2-BBBBB-CCCC format error codes are not supported.'
    return ''


def hex2err(error):
    error = int(error, 16)
    module = error & 0x1FF
    desc = (error >> 9) & 0x3FFF
    code = f'{module + 2000:04}-{desc:04}'
    return code


def get(error):
    if RE_APP.match(error):
        subs = error.split('-')
        mod = subs[1].casefold()
        code = int(subs[2], 10)
        sec_error = None
    elif not error.startswith('0x'):
        mod = int(error[:4], 10) - 2000
        code = int(error[5:9], 10)
        sec_error = err2hex(error)
    else:
        err_int = int(error, 16)
        mod = err_int & 0x1FF
        code = (err_int >> 9) & 0x3FFF
        sec_error = hex2err(error)

    ret = ConsoleErrorInfo(error, CONSOLE_NAME, COLOR, secondary_error=sec_error)
    module = modules.get(mod, Module('Unknown'))
    ret.add_field(ConsoleErrorField('Module', message_str=module.name, supplementary_value=mod))
    summary = module.get_summary(code)
    if summary:
        ret.add_field(ConsoleErrorField('Summary', message_str=summary))
    description = module.get_error(code)
    if description is None or not description.description:
        ret.add_field(ConsoleErrorField('Description', supplementary_value=code))
    else:
        ret.add_field(ConsoleErrorField('Description', message_str=description.description, supplementary_value=code))
        if description.support_url:
            ret.add_field(ConsoleErrorField('Further information', message_str=description.support_url))
        if description.is_ban:
            ret.add_field(BANNED_FIELD)
            ret.color = WARNING_COLOR

    return ret
