import json
import logging
import argparse
from typing import Dict

from clairvoyancex import graphql
from clairvoyancex import oracle


def parse_args():
    parser = argparse.ArgumentParser()

    defaults = {"document": "query { FUZZ }",
                "command": "POST"}

    parser.add_argument("-v", default=0, action="count")
    parser.add_argument(
        "-k",
        "--insecure",
        action="store_true",
        help="Disable server's certificate verification",
    )
    parser.add_argument(
        "--http2",
        action="store_true",
        help="Issue requests using HTTP version 2",
    )
    parser.add_argument(
        "-i",
        "--input",
        metavar="<file>",
        type=argparse.FileType("r"),
        help="Input file containing JSON schema which will be supplemented with obtained information",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<file>",
        help="Output file containing JSON schema (default to stdout)",
    )
    parser.add_argument(
        "-d",
        "--document",
        metavar="<string>",
        default=defaults["document"],
        help=f"Start with this document (default: %(default)s)",
    )
    parser.add_argument(
        "-x",
        "--proxy",
        metavar="[protocol://]host[:port]",
        help="Use this proxy",
    )
    parser.add_argument(
        "-X",
        "--request",
        dest="command",
        metavar="<command>",
        choices=["GET", "POST"],
        default=defaults["command"],
        help="Specify request command to  use (default: %(default)s). Options: %(choices)s",
    )
    parser.add_argument(
        "-H",
        "--header",
        metavar="<header>",
        dest="headers",
        action="append",
        default=[],
    )
    parser.add_argument(
        "-w",
        "--wordlist",
        metavar="<file>",
        required=True,
        type=argparse.FileType("r"),
        help="This wordlist will be used for all brute force effots (fields, arguments and so on)",
    )
    parser.add_argument("url")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    format = "[%(levelname)s][%(asctime)s %(filename)s:%(lineno)d]\t%(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    if args.v == 1:
        level = logging.INFO
    elif args.v > 1:
        level = logging.DEBUG
    else:
        level = logging.WARNING
    logging.basicConfig(level=level, format=format, datefmt=datefmt)

    config = graphql.Config()
    config.url = args.url
    config.verify = not args.insecure
    config.http2 = args.http2
    config.proxy = args.proxy
    config.command = args.command
    for h in args.headers:
        key, value = h.split(": ", 1)
        config.headers[key] = value

    with args.wordlist as f:
        wordlist = [w.strip() for w in f.readlines() if w.strip()]

    input_schema = None
    if args.input:
        with args.input as f:
            input_schema = json.load(f)

    input_document = args.document if args.document else None

    # check HTTP version used by server
    with graphql.new_client(http2=config.http2, verify=config.verify) as client:
        response = client.get(config.url)
        logging.info(f"Target server is using {response.http_version}")

    ignore = {"Int", "Float", "String", "Boolean", "ID"}
    while True:
        schema = oracle.clairvoyance(
            wordlist, config, input_schema=input_schema, input_document=input_document
        )

        if args.output:
            with open(args.output, "w") as f:
                f.write(schema)
        else:
            print(schema)

        input_schema = json.loads(schema)
        s = graphql.Schema(schema=input_schema)
        next = s.get_type_without_fields(ignore)
        ignore.add(next)
        if next:
            input_document = s.convert_path_to_document(s.get_path_from_root(next))
        else:
            break
