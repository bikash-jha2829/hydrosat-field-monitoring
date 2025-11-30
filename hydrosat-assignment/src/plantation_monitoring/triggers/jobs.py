"""Dagster job definitions for asset materialization."""

from dagster import define_asset_job

fields_job = define_asset_job(name="fields_job", selection=["fields"])
bbox_job = define_asset_job(name="bbox_job", selection=["bbox"])
