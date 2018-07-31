import argparse
import pathlib as pl
import typing as tp
import subprocess as sub
import math

CDDA_BITS_PER_FRAME = 588
CDDA_FRAMES_PER_SEC = 75
ACCURATERIP_DB_URL = 'http://www.accuraterip.com/accuraterip'

class ARDiscIds(tp.NamedTuple):
    disc_id_1: int
    disc_id_2: int
    cddb_disc_id: int

def create_accuraterip_db_url(disc_id_1: int, disc_id_2: int, cddb_disc_id: int, num_tracks: int) -> str:
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

def calc_ar_disc_ids(track_offsets: tp.Iterable[int]) -> ARDiscIds:
    disc_id_1 = 0
    disc_id_2 = 0
    cddb_disc_id = 0

    first_offset = None

    for track_num, track_offset in enumerate(track_offsets, start=0):
        if first_offset is None:
            first_offset = track_offset

        disc_id_1 += track_offset
        disc_id_2 += (track_offset if bool(track_offset) else 1) * (track_num + 1)

        if track_num < len(track_offsets) - 1:
            cddb_disc_id += sum_digits(int(track_offset // CDDA_FRAMES_PER_SEC) + 2)

    if first_offset is not None:
        cddb_disc_id = (
            ((cddb_disc_id % 255) << 24)
            + (((track_offset // CDDA_FRAMES_PER_SEC) - (first_offset // 75)) << 8)
            + (len(track_offsets) - 1)
        )

    disc_id_1 &= 0xFFFFFFFF
    disc_id_2 &= 0xFFFFFFFF
    cddb_disc_id &= 0xFFFFFFFF

    return ARDiscIds(disc_id_1, disc_id_2, cddb_disc_id)

def sum_digits(n: int) -> int:
    '''Sums the digits in an integer.'''
    r = 0

    while n > 0:
        r += n % 10
        n //= 10

    return r

if __name__ == '__main__':
    parser = get_arg_parser()
    parsed_args = parser.parse_args()

    flac_dir = parsed_args.flac_dir

    flac_files = get_flac_files_in_dir(flac_dir)

    for f in flac_files:
        print(f'Found file: {f.name}')

    track_offsets = list(yield_track_offsets(flac_files))
    print(track_offsets)

    ar_disc_ids = calc_ar_disc_ids(track_offsets)
    print(ar_disc_ids)

    print('Querying AccurateRip DB...')

    ar_db_url = create_accuraterip_db_url(*ar_disc_ids, len(flac_files))
    print(ar_db_url)
