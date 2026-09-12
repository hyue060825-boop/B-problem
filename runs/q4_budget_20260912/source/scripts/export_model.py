#!/usr/bin/env python3
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--checkpoint', required=True)
parser.add_argument('--output', required=True)
parser.parse_args()
raise SystemExit('NOT_RUN: export requires a real trained checkpoint; random initialization is not deployable')
