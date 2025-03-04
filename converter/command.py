import argparse
import sys
import os
import json
from pathlib import Path

from google.appengine.datastore import entity_bytes_pb2 as entity_pb2
from google.appengine.api import datastore
from google.appengine.api.datastore_types import EmbeddedEntity

from converter.exceptions import ValidationError, BaseError
from converter import records
from converter.utils import get_dest_dict, embedded_entity_to_dict, serialize_json


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="fs_to_json", description="Firestore DB export to JSON")

    parser.add_argument("-d", "--dest-dir",
                        help="Destination directory to store generated JSON",
                        type=str,
                        action="store",
                        default=None)

    parser.add_argument("source_dir", metavar='source_dir',
                        help="Destination directory to store generated JSON",
                        type=str,
                        action="store",
                        default=None)

    args = parser.parse_args(args)
    try:
        source_dir = os.path.abspath(args.source_dir)
        if not os.path.isdir(source_dir):
            raise ValidationError("Source directory does not exist.")
        if not args.dest_dir:
            dest_dir = os.path.join(source_dir, 'json')
        else:
            dest_dir = os.path.abspath(args.dest_dir)

        Path(dest_dir).mkdir(parents=True, exist_ok=True)

        if os.listdir(dest_dir):
            print("Destination directory is not empty. Deleting json files...")
            for f in Path(dest_dir).glob('*.json'):
                try:
                    print(f"Deleting file {f.name}")
                    f.unlink()
                except OSError as e:
                    print("Error: %s : %s" % (f, e.strerror))

        process_files(source_dir=source_dir, dest_dir=dest_dir)
    except BaseError as e:
        print(str(e))
        sys.exit(1)


def process_files(source_dir: str, dest_dir: str):
    json_tree = {}
    files = sorted(os.listdir(source_dir))
    documents = 0
    for filename in files:
        if not filename.startswith("output-"):
            continue
        print("Reading source from:" + filename)
        in_path = os.path.join(source_dir, filename)
        raw = open(in_path, 'rb')
        reader = records.RecordsReader(raw)
        for record in reader:
            entity_proto = entity_pb2.EntityProto()
            entity_proto.ParseFromString(record)
            ds_entity = datastore.Entity.FromPb(entity_proto)
            data = {}
            for name, value in list(ds_entity.items()):
                if isinstance(value, EmbeddedEntity):
                    dt = {}
                    data[name] = embedded_entity_to_dict(value, dt)
                else:
                    data[name] = value

            data_dict = get_dest_dict(ds_entity.key(), json_tree)
            data_dict.update(data)
            documents += 1

        out_file_path = os.path.join(dest_dir, filename + '.json')
        out = open(out_file_path, 'w', encoding='utf8')
        out.write(json.dumps(json_tree, default=serialize_json, ensure_ascii=False, indent=2))
        out.close()
        print("JSON file written to: " + out_file_path)
        json_tree = {}
    print(f"Total documents in collections : {documents}")


if __name__ == '__main__':
    main()
