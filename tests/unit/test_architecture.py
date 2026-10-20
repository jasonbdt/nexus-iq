"""Enforce inward dependencies and resource-free imports using the standard library."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import get_type_hints

from sqlmodel import SQLModel


def test_protocol_annotations_resolve_without_class_method_name_shadowing():
    """A port method named list must not replace the built-in annotation type."""
    from app.service_layer.ports import PatchNotes

    assert get_type_hints(PatchNotes.list)['return'] == list[dict]
    assert get_type_hints(PatchNotes.chunks)['return'] == list[dict] | None


def test_inner_layers_depend_only_on_domain_and_ports():
    root = Path(__file__).resolve().parents[2] / 'app'
    for layer in ('domain', 'service_layer'):
        for source in (root / layer).glob('*.py'):
            tree = ast.parse(source.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or '']
                else:
                    continue
                for module in modules:
                    if module.startswith('app.'):
                        assert module.startswith(('app.domain', 'app.service_layer')), source
                        assert layer != 'domain' or module.startswith('app.domain'), source
                    else:
                        assert module.split('.')[0] in sys.stdlib_module_names or node.level, source


def test_importing_app_needs_neither_secrets_nor_rq_nor_clients():
    environment = {key: value for key, value in os.environ.items()
                   if key not in ('JWT_SECRET', 'JWT_EXPIRES_IN', 'OPENAI_API_KEY', 'APP_KEY',
                                  'QDRANT_PORT', 'EMBEDDING_DIMENSION')}
    code = '''
import sys
from unittest.mock import patch
with patch('sqlmodel.create_engine', side_effect=AssertionError('DB opened')), \
     patch('openai.OpenAI', side_effect=AssertionError('SDK opened')), \
     patch('qdrant_client.AsyncQdrantClient', side_effect=AssertionError('Qdrant opened')):
    from app.main import create_app
    assert create_app().root_path == '/api/v1'
    assert 'rq' not in sys.modules
'''
    result = subprocess.run([sys.executable, '-c', code], env=environment,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_database_metadata_matches_pre_refactor_snapshot():
    actual = {}
    for name, table in sorted(SQLModel.metadata.tables.items()):
        actual[name] = {
            'columns': [{'name': col.name, 'type': str(col.type), 'nullable': col.nullable,
                         'primary_key': col.primary_key} for col in table.columns],
            'foreign_keys': sorted(str(fk.target_fullname) for fk in table.foreign_keys),
            'unique': sorted(sorted(col.name for col in constraint.columns)
                             for constraint in table.constraints
                             if constraint.__class__.__name__ == 'UniqueConstraint'),
            'indexes': sorted([index.name, index.unique, sorted(col.name for col in index.columns)]
                              for index in table.indexes),
        }
    baseline = Path(__file__).parents[1] / 'fixtures/database_schema.json'
    assert actual == json.loads(baseline.read_text(encoding='utf-8'))
