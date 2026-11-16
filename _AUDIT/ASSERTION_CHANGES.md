# Assertion change inventory

Compared with the PR bases: David-OS `6b147281` and Prediction_GUI `84250f26`. Includes Python `assert` and unittest `assert*` calls in changed Python files. Pure archive moves are excluded. Each block lists all changed assertions, including new regression tests. Existing assertions were not edited in the portability follow-up; new portability regression assertions are included.

## 1. David-OSv3/gui/filetagger_gui.py — FileTaggerPopup._run_process

The duplicate popup implementation was archived and replaced by a forwarder to Tagger v3. Its subprocess-stdout assertion moved with the historical implementation; the forwarder owns no subprocess. It was not removed to hide a failing test.

Before:
```python
# line 160
assert self.process.stdout is not None
```

## 2. David-OSv3/shared/identity/test_identity.py — test_current_registry_id_and_legacy_alias_both_validate

The identity schema now accepts registry_id alongside historical dotted ID aliases; the existing validation assertions still pass.

After:
```python
# line 73
assert parsed['series']=='MIM' and parsed['position']==0 and parsed['slug']=='Mephistopheles'
# line 74
assert I.parse_artifact_ref('MIM.00_Mephistopheles::audit')['role']=='audit'
# line 75
assert I.parse_document_id('DLAY.05.WATER')['slug']=='WATER'
# line 77
assert I.check_sidecar(sc)==[]
```

## 3. David-OSv3/tests/test_consolidation_acceptance.py — test_inventory_identity_tagger_prediction_gui_apply_rollback

Lock the real inventory → central identity → tagger → suggestion → GUI decision → apply/replay/rollback path. Identity and original bytes must survive across owners and restart.

After:
```python
# line 33
assert con.execute('SELECT registry_uuid FROM files WHERE path=?', (str(document),)).fetchone()[0] == issued['uuid7']
# line 40
assert con.execute('SELECT registry_uuid FROM registry_refs WHERE path=?',(str(document),)).fetchone()[0] == issued['uuid7']
# line 41
assert document.read_bytes() == original
# line 44
assert plan['rows'] and plan['rows'][0]['file']['registry_uuid'] == issued['uuid7']
# line 45
assert Path(plan['rows'][0]['target']).name == 'MIM.00_Mephistopheles.md'
# line 46
assert plan['rows'][0]['preference']['auto_approval'] is False
# line 54
assert port.isdigit(), process.stderr.read() if process.poll() is not None else 'GUI failed to start'
# line 60
assert con.execute('SELECT decision,actor FROM notification_decisions').fetchall() == [('approved','David')]
# line 64
assert run['status'] == 'applied'
# line 66
assert target.read_bytes() == original
# line 67
assert registry.reference(target)['uuid7'] == issued['uuid7']
# line 69
assert transaction.undo(Store(tmp_path/'fis-state'), run['id'])['conflicts'] == []
# line 70
assert document.read_bytes() == original and not target.exists()
# line 71
assert registry.reference(document)['uuid7'] == issued['uuid7']
```

## 4. David-OSv3/tests/test_fis_standalone.py — Independence.test_import_allowlist_and_no_delete_or_path_injection

The independent FIS boundary now explicitly permits the canonical identity, review and naming modules. This retains a closed import allowlist; inference/GUI/service dependencies remain forbidden.

Before:
```python
# line 141
self.assertIn(name.split('.')[0], sys.stdlib_module_names | {'fis', '__future__'}, (path, name))
```

After:
```python
# line 151
self.assertTrue(name in {'shared.meq_namer', 'shared.identity.registry', 'shared.review', 'prediction.naming.base', 'prediction.naming.features', 'prediction.naming.frequency', 'prediction.naming.markov_engine'} or name.split('.')[0] in allowed, (path, name))
```

## 5. David-OSv3/tests/test_identity_registry.py — test_alias_lookup_and_failed_batch_roll_back_all_assignments

Lock UUIDv7 issuance, explicit series assignments, legacy aliases, idempotent migration, concurrency, location history and separate identity after old-path reuse.

After:
```python
# line 92
assert r.lookup('W000001',scheme='work') == issued
# line 100
assert con.execute('SELECT count(*) FROM document_identities').fetchone()[0] == 1
# line 101
assert con.execute('SELECT count(*) FROM identity_locations').fetchone()[0] == 1
# line 102
assert con.execute('SELECT count(*) FROM identity_migrations').fetchone()[0] == 0
```

## 6. David-OSv3/tests/test_identity_registry.py — test_concurrent_issuance_has_one_winner

Lock UUIDv7 issuance, explicit series assignments, legacy aliases, idempotent migration, concurrency, location history and separate identity after old-path reuse.

After:
```python
# line 28
assert len({r['uuid7'] for r in rows}) == 1
```

## 7. David-OSv3/tests/test_identity_registry.py — test_explicit_migration_is_dry_by_default_and_atomic

Lock UUIDv7 issuance, explicit series assignments, legacy aliases, idempotent migration, concurrency, location history and separate identity after old-path reuse.

After:
```python
# line 76
assert not migrate(mapping, path)['applied'] and not path.exists()
# line 78
assert migrate(mapping, path, True) == first
# line 83
assert con.execute('SELECT count(*) FROM document_identities').fetchone()[0] == 1
```

## 8. David-OSv3/tests/test_identity_registry.py — test_issue_reopen_and_lookup

Lock UUIDv7 issuance, explicit series assignments, legacy aliases, idempotent migration, concurrency, location history and separate identity after old-path reuse.

After:
```python
# line 13
assert row['registry_id'] == 'MIM.00_Mephistopheles'
# line 15
assert token.version == 7 and token.variant == 'specified in RFC 4122'
# line 17
assert reopened.issue('MIM', 0, 'Mephistopheles') == row
# line 18
assert reopened.lookup(row['uuid7']) == reopened.lookup(row['registry_id']) == row
# line 19
assert reopened.lookup('unknown') is None
```

## 9. David-OSv3/tests/test_identity_registry.py — test_location_history_does_not_claim_a_reused_original_path

Lock UUIDv7 issuance, explicit series assignments, legacy aliases, idempotent migration, concurrency, location history and separate identity after old-path reuse.

After:
```python
# line 110
assert replacement['uuid7'] != original['uuid7']
# line 111
assert r.reference(tmp_path/'new.md')['uuid7'] == original['uuid7']
```

## 10. David-OSv3/tests/test_identity_registry.py — test_observation_assignment_and_move_preserve_one_uuid

Lock UUIDv7 issuance, explicit series assignments, legacy aliases, idempotent migration, concurrency, location history and separate identity after old-path reuse.

After:
```python
# line 53
assert ref['registry_id'] is None and UUID(ref['uuid7']).version == 7
# line 55
assert issued['uuid7'] == ref['uuid7']
# line 58
assert r.reference(destination)['uuid7'] == issued['uuid7']
# line 59
assert r.reference(source)['uuid7'] != issued['uuid7']
```

## 11. David-OSv3/tests/test_identity_registry.py — test_preserves_existing_stage1_tables

Lock UUIDv7 issuance, explicit series assignments, legacy aliases, idempotent migration, concurrency, location history and separate identity after old-path reuse.

After:
```python
# line 46
assert con.execute('SELECT * FROM works').fetchall() == [('legacy-work',)]
```

## 12. David-OSv3/tests/test_identity_registry.py — test_registry_does_not_merge_distinct_paths_by_content

Lock UUIDv7 issuance, explicit series assignments, legacy aliases, idempotent migration, concurrency, location history and separate identity after old-path reuse.

After:
```python
# line 66
assert r.reference(tmp_path/'a.md')['uuid7'] != r.reference(tmp_path/'b.md')['uuid7']
```

## 13. David-OSv3/tests/test_legacy_namer_review.py — test_legacy_batch_cannot_approve_its_own_predictions

High-confidence legacy suggestions must enter GUI review and cannot authorize their own mutations.

After:
```python
# line 11
assert counts['auto_approved']==0 and counts['queued']==1
# line 14
assert proposed and approved is None and 'GUI review required' in note
```

## 14. David-OSv3/tests/test_meq_namer.py — test_fis_classifier_uses_shared_scoring

Lock the extracted App 160 behavior (including unusual scoring rules), exact text formatting, shared function ownership and preservation of legacy evidence.

After:
```python
# line 69
assert fis_classifier.CHI_SIGNALS is m.CHI_SIGNALS
# line 70
assert fis_classifier.score_chi_factor is m.score_chi_factor
```

## 15. David-OSv3/tests/test_meq_namer.py — test_folder_address_falls_back_to_local_folder_metadata

Lock the extracted App 160 behavior (including unusual scoring rules), exact text formatting, shared function ownership and preservation of legacy evidence.

After:
```python
# line 60
assert result['address'].startswith('LOSS__Ordinary_folder__')
# line 61
assert result['trigger'] is None
# line 64
assert result['mode'] == 'meq'
```

## 16. David-OSv3/tests/test_meq_namer.py — test_folder_aggregate_excludes_unscored_and_keeps_rounding

Lock the extracted App 160 behavior (including unusual scoring rules), exact text formatting, shared function ownership and preservation of legacy evidence.

After:
```python
# line 51
assert m.folder_meq_aggregate(rows) == m.meq_namer_string({'G': 2, 'K': 2})
# line 52
assert m.folder_meq_aggregate([]) == ''
```

## 17. David-OSv3/tests/test_meq_namer.py — test_legacy_substrings_and_repeated_keywords

Lock the extracted App 160 behavior (including unusual scoring rules), exact text formatting, shared function ownership and preservation of legacy evidence.

After:
```python
# line 32
assert m.score_chi_factor('logos', 'K') == 1
# line 33
assert m.score_chi_factor('logos shannon', 'K') == 2
# line 34
assert m.score_chi_factor('graceful', 'G') == 1
```

## 18. David-OSv3/tests/test_meq_namer.py — test_lossless_address

Lock the extracted App 160 behavior (including unusual scoring rules), exact text formatting, shared function ownership and preservation of legacy evidence.

After:
```python
# line 43
assert r['address'] == f'{prefix}__{m.lossless_slug(title)}__{datetime.fromtimestamp(stamp):%Y-%m-%d}'
# line 44
assert r['basis'] == 'title_and_local_content_sample'
# line 45
assert m.lossless_slug('') == 'folder'
# line 46
assert len(m.lossless_slug('x' * 100)) == 40
```

## 19. David-OSv3/tests/test_meq_namer.py — test_retired_notes_are_preserved_instead_of_deleted

Lock the extracted App 160 behavior (including unusual scoring rules), exact text formatting, shared function ownership and preservation of legacy evidence.

After:
```python
# line 77
assert wipe_existing_fisnotes(tmp_path) == 2
# line 78
assert not list(tmp_path.glob('*.fisnote'))
# line 79
assert {p.read_bytes() for p in tmp_path.glob('.fisnote.legacy.*')} == {b'folder evidence', b'file evidence'}
```

## 20. David-OSv3/tests/test_meq_namer.py — test_scoring_boundaries

Lock the extracted App 160 behavior (including unusual scoring rules), exact text formatting, shared function ownership and preservation of legacy evidence.

After:
```python
# line 28
assert m.score_chi_factor(text.upper(), 'G') == expected
```

## 21. David-OSv3/tests/test_meq_namer.py — test_slot_and_pair_order

Lock the extracted App 160 behavior (including unusual scoring rules), exact text formatting, shared function ownership and preservation of legacy evidence.

After:
```python
# line 13
assert m.meq_namer_string(chi) == 'G3 M3 E3 S3 T3 K3 R3 Q3 F3 C3 :: [G.C] [M.F] [E.Q] [S.R] [T.K]'
# line 14
assert m.meq_namer_short({'K': 2, 'G': 1}) == 'G1 K2 :: [G.C] [T.K]'
# line 15
assert m.meq_namer_string({'G': 1}).startswith('G1 M0 E0 S0 T0 K0 R0 Q0 F0 C0 :: ')
```

## 22. David-OSv3/tests/test_meq_namer.py — test_unscored

Lock the extracted App 160 behavior (including unusual scoring rules), exact text formatting, shared function ownership and preservation of legacy evidence.

After:
```python
# line 20
assert m.meq_namer_string(chi) == m.meq_namer_short(chi) == ''
# line 21
assert (m.meq_namer_short(chi) or m.meq_namer_string(chi) or m.UNSCORED) == 'UNSCORED'
```

## 23. David-OSv3/tests/test_packaging_and_cli.py — test_pyproject_constrains_package_discovery_and_scripts

The wheel must include every consolidated canonical package, plus the already-present folder_hub and rule_brick packages. The old exact list was stale; the replacement remains an exact package allowlist.

Before:
```python
# line 11
assert project["tool"]["setuptools"]["packages"]["find"]["include"] == ["hub*", "engine*", "agents*", "pipeline*"]
```

After:
```python
# line 11
assert project["tool"]["setuptools"]["packages"]["find"]["include"] == ["hub*", "engine*", "agents*", "pipeline*", "folder_hub*", "rule_brick*", "shared*", "fis*", "prediction*", "Theophysics_Tagger*"]
```

## 24. David-OSv3/tests/test_portability.py — test_config_paths_resolve_against_config_file_and_environment_wins

Verify relocation-independent config paths, environment precedence, rejection of configured credentials, all-drive system-root protection and allowance of similarly named ordinary folders.

After:
```python
# line 17
assert path_setting('DAVID_OS_STATE_DIR', 'state_dir', 'unused') == folder / 'local state'
# line 20
assert path_setting('DAVID_OS_STATE_DIR', 'state_dir', 'unused') == override
```

## 25. David-OSv3/tests/test_portability.py — test_similar_folder_names_are_not_system_roots

Verify relocation-independent config paths, environment precedence, rejection of configured credentials, all-drive system-root protection and allowance of similarly named ordinary folders.

After:
```python
# line 40
assert not _is_system(path)
```

## 26. David-OSv3/tests/test_portability.py — test_system_roots_stay_protected_on_any_drive

Verify relocation-independent config paths, environment precedence, rejection of configured credentials, all-drive system-root protection and allowance of similarly named ordinary folders.

After:
```python
# line 34
assert _is_system(path)
# line 35
assert gate.unsafe(path, gate.defaults()) == 'system root'
```

## 27. David-OSv3/tests/test_review_contract.py — test_approval_binds_exact_rows_plan_and_survives_restart

Require exact immutable plan/row/actor/decision binding and reject edited, stale, held or replayed approvals.

After:
```python
# line 23
assert run['status'] == 'applied'
# line 25
assert store.registry.reference(new_path)['uuid7'] == plan['rows'][0]['file']['registry_uuid']
# line 26
assert transaction.undo(Store(tmp_path/'state'), run['id'])['conflicts'] == []
# line 27
assert {p.name: p.read_bytes() for p in root.iterdir()} == before
```

## 28. David-OSv3/tests/test_review_contract.py — test_registry_target_conflict_stops_before_source_mutation

Require exact immutable plan/row/actor/decision binding and reject edited, stale, held or replayed approvals.

After:
```python
# line 51
assert source.read_text()=='A method and evidence'
# line 52
assert not Path(row['target']).exists()
```

## 29. David-OSv3/tests/test_review_contract.py — test_restart_recovers_file_move_before_registry_commit

Require exact immutable plan/row/actor/decision binding and reject edited, stale, held or replayed approvals.

After:
```python
# line 67
assert transaction.undo(restarted,run['id'])['conflicts']==[]
# line 68
assert source.read_text()=='A method and evidence'
# line 69
assert restarted.registry.reference(source)['uuid7']==row['file']['registry_uuid']
```

## 30. David-OSv3/tests/test_tagger_v3_compatibility.py — test_legacy_catalog_is_preserved_and_options_forward

Lock compatibility arguments, exclusion filters and historical folder IDs while delegating work to Tagger v3 and central issuance.

After:
```python
# line 13
assert args[:2] == ['scan','--catalog']
# line 14
assert args[args.index('--db')+1] == str(tmp_path/'legacy.tagger3.db')
# line 15
assert '--write-sidecars' in args and '--force' in args
# line 16
assert '--full-hash' not in args
# line 17
assert db.read_bytes() == before
```

## 31. David-OSv3/tests/test_tagger_v3_compatibility.py — test_legacy_marker_renderer_uses_registry_uuid_and_blocks_remint

Lock compatibility arguments, exclusion filters and historical folder IDs while delegating work to Tagger v3 and central issuance.

After:
```python
# line 28
assert UUID(token).version == 7
# line 29
assert token in render(tmp_path,tmp_path)
```

## 32. David-OSv3/tests/test_tagger_v3_compatibility.py — test_legacy_watch_preserves_explicit_roots_and_exclusions

Lock compatibility arguments, exclusion filters and historical folder IDs while delegating work to Tagger v3 and central issuance.

After:
```python
# line 44
assert args[0]=='watch' and args.count('--source')==2
# line 45
assert 'private' in fake.SKIP_DIRS and 'secret.txt' in fake.SKIP_NAMES
```

## 33. David-OSv3/tests/test_tagger_v3_compatibility.py — test_old_marker_id_is_an_alias_with_a_registry_reference

Lock compatibility arguments, exclusion filters and historical folder IDs while delegating work to Tagger v3 and central issuance.

After:
```python
# line 56
assert 'folder_id: OLD-FOLDER' in text and f"registry_uuid: {reference['uuid7']}" in text
# line 57
assert registry.lookup('OLD-FOLDER',scheme='legacy-folder-id')==reference
```

## 34. David-OSv3/tools/filetagger/filetagger_gui.py — FileTaggerPopup._run_process

The duplicate popup implementation was archived and replaced by a forwarder to Tagger v3. Its subprocess-stdout assertion moved with the historical implementation; the forwarder owns no subprocess. It was not removed to hide a failing test.

Before:
```python
# line 157
assert self.process.stdout is not None
```

## 35. Prediction_GUI/tests/test_fis_review.py — FISReviewTests.test_edits_holds_and_modified_plan_cannot_approve

Require exact immutable plan/row/actor/decision binding, reject changed or held plans, and persist explicit decisions across reopening.

After:
```python
# line 45
self.assertRaises(ValueError)
# line 47
self.assertRaises(ValueError)
# line 49
self.assertRaises(ValueError)
# line 50
self.assertTrue(all(i['status']=='pending' for i in self.engine.store.items(batch)))
```

## 36. Prediction_GUI/tests/test_fis_review.py — FISReviewTests.test_exact_receipt_and_restart

Require exact immutable plan/row/actor/decision binding, reject changed or held plans, and persist explicit decisions across reopening.

After:
```python
# line 25
self.assertEqual(batch, submit_plan(self.engine, self.plan))
# line 29
self.assertEqual(receipt, decide(second, self.plan, ['r1'], 'approved', 'David'))
# line 30
self.assertEqual(second.store.items(batch)[0]['status'], 'approved')
# line 31
self.assertRaises(ValueError)
# line 32
self.assertTrue(meq_namer_string({'G':3}).startswith('G3 M0'))
```

## 37. Prediction_GUI/tests/test_fis_review.py — FISReviewTests.test_receipt_cannot_claim_a_competing_actors_choice

Require exact immutable plan/row/actor/decision binding, reject changed or held plans, and persist explicit decisions across reopening.

After:
```python
# line 40
self.assertRaisesRegex(ValueError, 'recorded decision differs')
```

## 38. Prediction_GUI/tests/test_notifications.py — NotificationEngineTests.test_gui_never_auto_approves_suggestions

Confidence is advisory. Both rows must stay pending until an explicit GUI decision; the old expected automatic approval violated the reviewed mutation boundary.

After:
```python
# line 39
self.assertEqual([i["status"] for i in self.engine.store.items(batch)], ["pending", "pending"])
```

## 39. Prediction_GUI/tests/test_notifications.py — NotificationEngineTests.test_only_explicit_safe_work_auto_approves

Confidence is advisory. Both rows must stay pending until an explicit GUI decision; the old expected automatic approval violated the reviewed mutation boundary.

Before:
```python
# line 39
self.assertEqual([i["status"] for i in self.engine.store.items(batch)], ["approved", "pending"])
```

## Review of replacements

There are three pre-existing test expectation changes (the notification test was also renamed): the FIS import boundary, the wheel package list, and notification auto-approval. The other changes add regression assertions. The first two retain exact allowlists; the third tightens approval behavior. Two runtime stdout assertions also disappear from the active duplicate popup files when those implementations are archived; they remain preserved in the archived originals. None suppress test failures or weaken identity/rollback checks.
