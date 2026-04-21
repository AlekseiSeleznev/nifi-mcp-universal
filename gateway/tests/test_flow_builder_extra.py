from __future__ import annotations

from gateway.nifi.flow_builder import (
    FlowBuilderGuide,
    FlowPatternLibrary,
    FlowPositioner,
    FlowRequirement,
    FlowTemplate,
    analyze_flow_request,
)


def test_all_listed_templates_resolve_and_unknown_returns_none():
    for item in FlowPatternLibrary.list_available_templates():
        template = FlowPatternLibrary.get_template(item["key"])
        assert template is not None
        assert template.name

    assert FlowPatternLibrary.get_template("database_sync") is not None
    assert FlowPatternLibrary.get_template("database") is not None
    assert FlowPatternLibrary.get_template("unknown-template") is None


def test_identify_pattern_covers_specific_branches():
    cases = {
        "sync mysql to postgres": "Database to Database",
        "load csv files into postgres": "Files to Database",
        "export mysql data and save as json files": "Database to Files",
        "watch a file folder for new arrivals": "File Watcher to Processing",
        "stream kafka events into database": "Streaming to Database",
        "ship kafka data to s3": "Kafka to S3",
        "load from object storage bucket into database": "Object Storage to Database",
        "collect logs and aggregate them": "Log Aggregation",
        "poll sftp for files": "FTP/SFTP to Processing",
        "call rest api into database": "REST API to Database",
        "convert csv to parquet": "Data Transformation",
        "replicate sql server to iceberg": "SQL Server to Iceberg",
    }

    for request, expected_name in cases.items():
        template = FlowBuilderGuide.identify_pattern(request)
        assert template is not None
        assert template.name == expected_name

    assert FlowBuilderGuide.identify_pattern("do something vague") is None


def test_format_requirements_validate_and_position_helpers():
    template = FlowTemplate(
        name="Custom Flow",
        description="desc",
        requirements=[
            FlowRequirement("required_name", "required desc", True, default="default-value", example="example-value"),
            FlowRequirement("optional_name", "optional desc", False, default="opt-default", example="opt-example"),
        ],
        processor_types=["A"],
    )

    formatted = FlowBuilderGuide.format_requirements_for_user(template)
    assert "Required Information" in formatted
    assert "Optional Information" in formatted
    assert "example-value" in formatted
    assert "opt-default" in formatted

    valid, missing = FlowBuilderGuide.validate_requirements(template, {"required_name": "x"})
    assert valid is True
    assert missing == []

    valid, missing = FlowBuilderGuide.validate_requirements(template, {"required_name": "   "})
    assert valid is False
    assert missing == ["required_name"]

    assert FlowPositioner.linear_flow(3) == [(100, 200), (450, 200), (800, 200)]
    assert len(FlowPositioner.branching_flow(2, 3)) == 5


def test_analyze_flow_request_reports_missing_pattern_templates():
    found = analyze_flow_request("load csv files into postgres")
    assert found["pattern_found"] is True
    assert found["requirement_count"] > 0

    not_found = analyze_flow_request("something custom and strange")
    assert not_found["pattern_found"] is False
    assert "Available templates" in not_found["message"]


def test_identify_pattern_database_sync_without_target_is_not_enough():
    assert FlowBuilderGuide.identify_pattern("sync database changes continuously") is None


def test_format_requirements_without_required_or_optional_examples():
    template = FlowTemplate(
        name="Optional Only",
        description="desc",
        requirements=[
            FlowRequirement("required_name", "required desc", True, default="default-only"),
            FlowRequirement("optional_name", "optional desc", False, default="opt-default"),
        ],
    )
    formatted = FlowBuilderGuide.format_requirements_for_user(template)
    assert "Required Information" in formatted
    assert "Optional Information" in formatted
    assert "default-only" in formatted
    assert "opt-default" in formatted

    optional_only = FlowTemplate(
        name="Optional Flow",
        description="desc",
        requirements=[FlowRequirement("optional_name", "optional desc", False, default="opt-default")],
    )
    formatted_optional = FlowBuilderGuide.format_requirements_for_user(optional_only)
    assert "Required Information" not in formatted_optional
