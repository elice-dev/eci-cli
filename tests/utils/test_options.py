from __future__ import annotations

import click
from click.testing import CliRunner

from app.utils.options import FilterSpec, filter_options, output_options


def test_filter_spec_defaults():
    spec = FilterSpec("name_ilike")
    assert spec.name == "name_ilike"
    assert spec.type == "string"
    assert spec.help == ""
    assert spec.resolver is None


def test_filter_options_attaches_click_options():
    runner = CliRunner()

    @click.command()
    @filter_options(
        [
            FilterSpec("name_ilike", help="match name"),
            FilterSpec("activated", type="bool"),
        ]
    )
    def cmd(name_ilike, activated):
        click.echo(f"{name_ilike}:{activated}")

    result = runner.invoke(cmd, ["--name-ilike", "abc", "--activated", "true"])
    assert result.exit_code == 0
    assert result.output.strip() == "abc:True"


def test_output_options_defaults_to_table_format():
    runner = CliRunner()

    @click.command()
    @output_options
    def cmd(fmt, query):
        click.echo(f"{fmt}|{query}")

    result = runner.invoke(cmd, [])
    assert result.exit_code == 0
    assert result.output.strip() == "table|None"


def test_output_options_accepts_json_and_query():
    runner = CliRunner()

    @click.command()
    @output_options
    def cmd(fmt, query):
        click.echo(f"{fmt}|{query}")

    result = runner.invoke(cmd, ["--format", "json", "--query", "a,b"])
    assert result.exit_code == 0
    assert result.output.strip() == "json|a,b"
