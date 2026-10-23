use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;
use walkdir::{DirEntry, WalkDir};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanOptions {
    pub extension_swamp_threshold: usize,
    pub flat_overload_threshold: usize,
    pub path_length_threshold: usize,
}

impl Default for ScanOptions {
    fn default() -> Self {
        Self {
            extension_swamp_threshold: 8,
            flat_overload_threshold: 200,
            path_length_threshold: 200,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileRecord {
    pub path: PathBuf,
    pub relative_path: PathBuf,
    pub parent: PathBuf,
    pub extension: String,
    pub size_bytes: u64,
    pub modified_unix: Option<u64>,
    pub blake3: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Symptom {
    pub id: String,
    pub severity: String,
    pub path: PathBuf,
    pub evidence: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanReport {
    pub schema: String,
    pub mode: String,
    pub root: PathBuf,
    pub files: Vec<FileRecord>,
    pub symptoms: Vec<Symptom>,
    pub errors: Vec<String>,
}

fn should_descend(entry: &DirEntry) -> bool {
    if !entry.file_type().is_dir() || entry.depth() == 0 {
        return true;
    }
    !matches!(
        entry
            .file_name()
            .to_string_lossy()
            .to_ascii_lowercase()
            .as_str(),
        ".git" | "node_modules" | "target" | ".venv" | "venv" | "__pycache__"
    )
}

fn hash_file(path: &Path) -> Result<String> {
    let mut reader = fs::File::open(path).with_context(|| format!("opening {}", path.display()))?;
    let mut hasher = blake3::Hasher::new();
    std::io::copy(&mut reader, &mut hasher)
        .with_context(|| format!("hashing {}", path.display()))?;
    Ok(hasher.finalize().to_hex().to_string())
}

fn looks_versioned(name: &str) -> bool {
    let value = name.to_ascii_lowercase();
    value.contains("_final")
        || value.contains(" final")
        || value.contains("_copy")
        || value.contains(" copy")
        || value.contains("(1)")
        || value.contains("(2)")
        || (1..=20).any(|n| value.contains(&format!("_v{n}")))
}

fn config_leak_name(name: &str) -> bool {
    let value = name.to_ascii_lowercase();
    value == ".env"
        || value.starts_with(".env.")
        || value.contains("api_key")
        || value.contains("apikey")
        || value.contains("secret")
        || value.contains("token")
}

fn program_root_markers(path: &Path) -> Vec<&'static str> {
    [
        ".git",
        "Cargo.toml",
        "package.json",
        "requirements.txt",
        "pyproject.toml",
    ]
    .into_iter()
    .filter(|marker| path.join(marker).exists())
    .collect()
}

pub fn scan(root: &Path, options: &ScanOptions) -> ScanReport {
    let root = root.canonicalize().unwrap_or_else(|_| root.to_path_buf());
    let mut files = Vec::new();
    let mut errors = Vec::new();
    let mut symptoms = Vec::new();
    let mut folders = BTreeSet::new();

    for item in WalkDir::new(&root)
        .follow_links(false)
        .into_iter()
        .filter_entry(should_descend)
    {
        let entry = match item {
            Ok(entry) => entry,
            Err(error) => {
                errors.push(error.to_string());
                continue;
            }
        };
        let path = entry.path();
        if entry.file_type().is_dir() {
            folders.insert(path.to_path_buf());
            continue;
        }
        if !entry.file_type().is_file() {
            continue;
        }
        let metadata = match entry.metadata() {
            Ok(value) => value,
            Err(error) => {
                errors.push(format!("{}: {error}", path.display()));
                continue;
            }
        };
        let hash = match hash_file(path) {
            Ok(value) => value,
            Err(error) => {
                errors.push(error.to_string());
                continue;
            }
        };
        let parent = path.parent().unwrap_or(&root).to_path_buf();
        let relative_path = path.strip_prefix(&root).unwrap_or(path).to_path_buf();
        let extension = path
            .extension()
            .map(|value| value.to_string_lossy().to_ascii_lowercase())
            .unwrap_or_default();
        let modified_unix = metadata
            .modified()
            .ok()
            .and_then(|value| value.duration_since(UNIX_EPOCH).ok())
            .map(|value| value.as_secs());
        files.push(FileRecord {
            path: path.to_path_buf(),
            relative_path,
            parent,
            extension,
            size_bytes: metadata.len(),
            modified_unix,
            blake3: hash,
        });
    }

    for folder in folders {
        let markers = program_root_markers(&folder);
        if !markers.is_empty() {
            symptoms.push(Symptom {
                id: "I01".into(),
                severity: "critical".into(),
                path: folder.clone(),
                evidence: format!("program-root markers: {}", markers.join(", ")),
            });
        }
        let direct: Vec<_> = files.iter().filter(|file| file.parent == folder).collect();
        let extensions: BTreeSet<_> = direct.iter().map(|file| file.extension.as_str()).collect();
        if extensions.len() > options.extension_swamp_threshold {
            symptoms.push(Symptom {
                id: "S01".into(),
                severity: "medium".into(),
                path: folder.clone(),
                evidence: format!("{} distinct extensions", extensions.len()),
            });
        }
        if direct.len() > options.flat_overload_threshold {
            symptoms.push(Symptom {
                id: "S04".into(),
                severity: "medium".into(),
                path: folder.clone(),
                evidence: format!("{} direct files", direct.len()),
            });
        }
    }

    for file in &files {
        let name = file.path.file_name().unwrap_or_default().to_string_lossy();
        if looks_versioned(&name) {
            symptoms.push(Symptom {
                id: "S02".into(),
                severity: "medium".into(),
                path: file.path.clone(),
                evidence: "version-like filename".into(),
            });
        }
        if config_leak_name(&name) {
            symptoms.push(Symptom {
                id: "I03".into(),
                severity: "critical".into(),
                path: file.path.clone(),
                evidence: "sensitive filename pattern; contents not read for this check".into(),
            });
        }
        if file.path.to_string_lossy().chars().count() > options.path_length_threshold {
            symptoms.push(Symptom {
                id: "N04".into(),
                severity: "medium".into(),
                path: file.path.clone(),
                evidence: format!("path length exceeds {}", options.path_length_threshold),
            });
        }
    }

    let mut hashes: BTreeMap<&str, Vec<&FileRecord>> = BTreeMap::new();
    for file in &files {
        hashes.entry(&file.blake3).or_default().push(file);
    }
    for group in hashes.values().filter(|group| group.len() > 1) {
        symptoms.push(Symptom {
            id: "C01".into(),
            severity: "medium".into(),
            path: group[0].parent.clone(),
            evidence: format!(
                "{} byte-identical files: {}",
                group.len(),
                group
                    .iter()
                    .map(|file| file.relative_path.display().to_string())
                    .collect::<Vec<_>>()
                    .join(" | ")
            ),
        });
    }

    symptoms.sort_by(|a, b| (&a.id, &a.path).cmp(&(&b.id, &b.path)));
    ScanReport {
        schema: "fis.scan-report.v0.1".into(),
        mode: "READ_ONLY".into(),
        root,
        files,
        symptoms,
        errors,
    }
}

pub fn render_markdown(report: &ScanReport) -> String {
    let mut out = String::new();
    out.push_str("# FIS Rust Kernel — Read-Only Report\n\n");
    out.push_str(&format!("- Root: `{}`\n", report.root.display()));
    out.push_str(&format!("- Files: {}\n", report.files.len()));
    out.push_str(&format!("- Symptoms: {}\n", report.symptoms.len()));
    out.push_str(&format!("- Errors: {}\n", report.errors.len()));
    out.push_str("- Mutation performed: **NO**\n\n## Symptoms\n\n");
    if report.symptoms.is_empty() {
        out.push_str("No implemented symptoms were detected.\n");
    } else {
        for symptom in &report.symptoms {
            out.push_str(&format!(
                "- **{} / {}** — `{}` — {}\n",
                symptom.id,
                symptom.severity,
                symptom.path.display(),
                symptom.evidence
            ));
        }
    }
    if !report.errors.is_empty() {
        out.push_str("\n## Errors\n\n");
        for error in &report.errors {
            out.push_str(&format!("- {error}\n"));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn detects_program_root_versioning_sensitive_names_and_duplicates() {
        let temp = tempdir().unwrap();
        fs::write(temp.path().join("Cargo.toml"), "[package]").unwrap();
        fs::write(temp.path().join("paper_v2.md"), "same").unwrap();
        fs::write(temp.path().join("paper_copy.md"), "same").unwrap();
        fs::write(temp.path().join(".env"), "not inspected").unwrap();

        let report = scan(temp.path(), &ScanOptions::default());
        let ids: BTreeSet<_> = report
            .symptoms
            .iter()
            .map(|item| item.id.as_str())
            .collect();
        assert!(ids.contains("I01"));
        assert!(ids.contains("I03"));
        assert!(ids.contains("S02"));
        assert!(ids.contains("C01"));
        assert_eq!(report.mode, "READ_ONLY");
    }
}
