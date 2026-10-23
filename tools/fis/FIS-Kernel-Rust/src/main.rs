use anyhow::{Context, Result, bail};
use clap::Parser;
use fis_kernel::{ScanOptions, render_markdown, scan};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Parser, Debug)]
#[command(about = "Read-only filesystem intelligence proof of concept")]
struct Args {
    #[arg(value_name = "ROOT")]
    root: PathBuf,

    #[arg(long, value_name = "DIRECTORY")]
    out: Option<PathBuf>,

    #[arg(long, default_value_t = 8)]
    extension_threshold: usize,

    #[arg(long, default_value_t = 200)]
    flat_threshold: usize,
}

fn absolute(path: &Path) -> Result<PathBuf> {
    if path.is_absolute() {
        Ok(path.to_path_buf())
    } else {
        Ok(std::env::current_dir()?.join(path))
    }
}

fn main() -> Result<()> {
    let args = Args::parse();
    let root = args
        .root
        .canonicalize()
        .with_context(|| format!("invalid scan root {}", args.root.display()))?;
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs();
    let out = absolute(
        args.out.as_deref().unwrap_or(
            &std::env::temp_dir()
                .join("fis-kernel-rust")
                .join(stamp.to_string()),
        ),
    )?;
    if out.starts_with(&root) {
        bail!("output directory must be outside the scanned root");
    }
    fs::create_dir_all(&out)?;

    let report = scan(
        &root,
        &ScanOptions {
            extension_swamp_threshold: args.extension_threshold,
            flat_overload_threshold: args.flat_threshold,
            ..ScanOptions::default()
        },
    );
    fs::write(
        out.join("scan-report.json"),
        serde_json::to_vec_pretty(&report)?,
    )?;
    fs::write(out.join("REPORT.md"), render_markdown(&report))?;
    println!(
        "files={} symptoms={} errors={} output={}",
        report.files.len(),
        report.symptoms.len(),
        report.errors.len(),
        out.display()
    );
    Ok(())
}
