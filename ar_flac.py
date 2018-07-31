import argparse
import pathlib as pl
import typing as tp
import subprocess as sub
import math

CDDA_BITS_PER_FRAME = 588

class TrackInfo(tp.NamedTuple):
    offset: int
    length: int
    num_samples: int

def get_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Validate FLAC files against the online AccurateRip database.')

    parser.add_argument('flac_dir', type=pl.Path, help='directory to look for FLAC files in')

    return parser

def get_flac_files_in_dir(dir_path: pl.Path) -> tp.List[pl.Path]:
    return sorted(dir_path.glob('*.flac'))

def get_track_data(flac_files: tp.Iterable[pl.Path]) -> tp.Generator[TrackInfo, None, None]:
    offset = 0

    for f in flac_files:
        # Use `metaflac` to get track offsets, lengths, and samples.
        process_args = ('metaflac', '--show-total-samples', str(f))
        num_samples = int(sub.check_output(process_args))
        print(f'# of samples: {num_samples}')

        length = int(math.ceil(num_samples / CDDA_BITS_PER_FRAME))
        print(f'Length: {length}')

        yield TrackInfo(offset, length, num_samples)

        offset += length

if __name__ == '__main__':
    parser = get_arg_parser()
    parsed_args = parser.parse_args()

    flac_dir = parsed_args.flac_dir

    flac_files = get_flac_files_in_dir(flac_dir)

    for f in flac_files:
        print(f'Found file: {f.name}')

    print(list(get_track_data(flac_files)))
