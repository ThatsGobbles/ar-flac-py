import argparse
import pathlib as pl

def get_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Validate FLAC files against the online AccurateRip database.')

    parser.add_argument('flac_dir', type=pl.Path, help='directory to look for FLAC files in')

    return parser

if __name__ == '__main__':
    parser = get_arg_parser()
    parsed_args = parser.parse_args()

    print(parsed_args.flac_dir)
    print(type(parsed_args.flac_dir))

