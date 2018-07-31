import argparse
import pathlib as pl
import typing as tp

def get_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Validate FLAC files against the online AccurateRip database.')

    parser.add_argument('flac_dir', type=pl.Path, help='directory to look for FLAC files in')

    return parser

def get_flac_files_in_dir(dir_path: pl.Path) -> tp.List[pl.Path]:
    return sorted(dir_path.glob('*.flac'))

if __name__ == '__main__':
    parser = get_arg_parser()
    parsed_args = parser.parse_args()

    flac_dir = parsed_args.flac_dir

    for f in get_flac_files_in_dir(flac_dir):
        print(f'Found file: {f.name}')
