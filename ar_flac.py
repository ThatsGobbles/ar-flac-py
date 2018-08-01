import argparse
import pathlib as pl
import typing as tp
import subprocess as sub
import math
import struct

import requests as req

CDDA_BITS_PER_FRAME = 588
CDDA_FRAMES_PER_SEC = 75
ACCURATERIP_DB_URL = 'http://www.accuraterip.com/accuraterip'


class ARDiscInfo(tp.NamedTuple):
    disc_id_1: int
    disc_id_2: int
    cddb_disc_id: int
    num_tracks: int

class ARTrackInfo(tp.NamedTuple):
    confidence: int
    crc: int


def create_accuraterip_db_url(ar_disc_info: ARDiscInfo) -> str:
    disc_id_1 = ar_disc_info.disc_id_1
    disc_id_2 = ar_disc_info.disc_id_2
    cddb_disc_id = ar_disc_info.cddb_disc_id
    num_tracks = ar_disc_info.num_tracks

    sub_comps = (
        ACCURATERIP_DB_URL,
        f'{disc_id_1 & 0xF:x}',
        f'{disc_id_1 >> 4 & 0xF:x}',
        f'{disc_id_1 >> 8 & 0xF:x}',
        f'dBAR-{num_tracks:0>3d}-{disc_id_1:0>8x}-{disc_id_2:0>8x}-{cddb_disc_id:0>8x}.bin',
    )

    url = '/'.join(sub_comps)

    return url

def get_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Validate FLAC files against the online AccurateRip database.')

    parser.add_argument('flac_dir', type=pl.Path, help='directory to look for FLAC files in')

    return parser

def get_flac_files_in_dir(dir_path: pl.Path) -> tp.List[pl.Path]:
    return sorted(dir_path.glob('*.flac'))

def yield_track_offsets(flac_files: tp.Iterable[pl.Path]) -> tp.Generator[int, None, None]:
    offset = 0

    for f in flac_files:
        yield offset

        # Use `metaflac` to get track lengths/samples.
        process_args = ('metaflac', '--show-total-samples', str(f))
        num_samples = int(sub.check_output(process_args))
        # print(f'# of samples: {num_samples}')

        length = int(math.ceil(num_samples / CDDA_BITS_PER_FRAME))
        # print(f'Length: {length}')

        offset += length

    # Yield the offset after the final track.
    yield offset

def calc_ar_disc_info(track_offsets: tp.Iterable[int]) -> ARDiscInfo:
    disc_id_1 = 0
    disc_id_2 = 0
    cddb_disc_id = 0

    first_offset = None
    num_tracks = len(track_offsets) - 1

    for track_num, track_offset in enumerate(track_offsets, start=0):
        if first_offset is None:
            first_offset = track_offset

        disc_id_1 += track_offset
        disc_id_2 += (track_offset if bool(track_offset) else 1) * (track_num + 1)

        if track_num < num_tracks:
            cddb_disc_id += sum_digits(int(track_offset // CDDA_FRAMES_PER_SEC) + 2)

    if first_offset is not None:
        cddb_disc_id = (
            ((cddb_disc_id % 255) << 24)
            + (((track_offset // CDDA_FRAMES_PER_SEC) - (first_offset // 75)) << 8)
            + num_tracks
        )

    disc_id_1 &= 0xFFFFFFFF
    disc_id_2 &= 0xFFFFFFFF
    cddb_disc_id &= 0xFFFFFFFF

    return ARDiscInfo(disc_id_1, disc_id_2, cddb_disc_id, num_tracks)

def sum_digits(n: int) -> int:
    '''Sums the digits in a non-negative integer.'''
    r = 0

    while n > 0:
        r += n % 10
        n //= 10

    return r

def yield_data_from_bin(ar_bin_data: bytes, ar_disc_info: ARDiscInfo) -> tp.Generator[ARTrackInfo, None, None]:
    print(f'Extracting CRCs from BIN data, {len(ar_bin_data)} byte(s)')

    # The header data consists of the first 13 bytes.
    header_data = ar_bin_data[:13]

    # The remaining data is per-track confidence and CRC data.
    per_track_data = ar_bin_data[13:]

    # Stored as little-endian: i8, u32, u32, u32.
    num_tracks, disc_id_1, disc_id_2, cddb_disc_id = struct.unpack('<bIII', header_data)

    assert num_tracks == ar_disc_info.num_tracks
    assert disc_id_1 == ar_disc_info.disc_id_1
    assert disc_id_2 == ar_disc_info.disc_id_2
    assert cddb_disc_id == ar_disc_info.cddb_disc_id

    print(num_tracks, disc_id_1, disc_id_2, cddb_disc_id)

    for i, (conf, crc, _) in enumerate(struct.iter_unpack('<bII', per_track_data), start=1):
        yield(ARTrackInfo(confidence=conf, crc=crc))
        print(f'Track {i}: conf={conf}, crc={crc}')

def yield_crcs_from_flac_files(flac_files: tp.Iterable[pl.Path]) -> tp.Generator[int, None, None]:
    is_first = True

    for f, is_last in lookahead(flac_files):
        process_args = (
            'flac',
            '-d',
            '-c',
            '-f',
            '--force-raw-format',
            '--totally-silent',
            '--endian=little',
            '--sign=signed',
            str(f),
        )

        audio_data = sub.check_output(process_args)

        # For the first track, chop off the first 2939 samples.
        # For the last track, chop off the last 2940 samples (exactly 5 frames).
        # Note that for an album with only one track, that track will be both first AND last!

        if is_first:
            is_first = False

        if is_last:
            pass

        yield 0

T = tp.TypeVar('T')

def lookahead(iterable: tp.Iterable[T]) -> tp.Generator[T, None, None]:
    '''Pass through all values from the given iterable,
    along with a flag indicating if that element is the last one.'''
    # Get an iterator and pull the first value.
    it = iter(iterable)
    last = next(it)

    # Run the iterator to exhaustion (starting from the second value).
    for val in it:
        # Report the *previous* value (more to come).
        yield last, False
        last = val

    # Report the last value.
    yield last, True


if __name__ == '__main__':
    parser = get_arg_parser()
    parsed_args = parser.parse_args()

    flac_dir = parsed_args.flac_dir

    flac_files = get_flac_files_in_dir(flac_dir)

    for f in flac_files:
        print(f'Found file: {f.name}')

    track_offsets = list(yield_track_offsets(flac_files))
    print(track_offsets)

    ar_disc_info = calc_ar_disc_info(track_offsets)
    print(ar_disc_info)

    print('Querying AccurateRip DB...')

    ar_db_url = create_accuraterip_db_url(ar_disc_info)
    print(ar_db_url)

    response = req.get(ar_db_url)

    # TODO: Handle 404 errors more gracefully.
    response.raise_for_status()

    ar_bin_data = response.content

    bin_data = list(yield_data_from_bin(ar_bin_data, ar_disc_info))

    list(yield_crcs_from_flac_files(flac_files))
