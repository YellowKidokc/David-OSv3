//! FIS MinHash accelerator.
//! Bit-identical to fingerprint.py::minhash_signature:
//!   h_i(s) = int(md5(f"{i}:{s}").hexdigest(), 16), signature[i] = min over shingles.
//!
//! Protocol (stdin -> stdout, UTF-8):
//!   first line: num_hashes
//!   then for each document: a line "#DOC" followed by one shingle per line.
//!   Output: one line per document, num_hashes space-separated decimal u128 values.
use md5::{Digest, Md5};
use std::io::{self, BufRead, BufWriter, Write};

fn signature(shingles: &[String], n: usize) -> Vec<u128> {
    let mut sig = vec![u128::MAX; n];
    let mut buf = Vec::with_capacity(256);
    for s in shingles {
        for (i, slot) in sig.iter_mut().enumerate() {
            buf.clear();
            buf.extend_from_slice(i.to_string().as_bytes());
            buf.push(b':');
            buf.extend_from_slice(s.as_bytes());
            let h = u128::from_be_bytes(Md5::digest(&buf).into());
            if h < *slot {
                *slot = h;
            }
        }
    }
    sig
}

fn main() -> io::Result<()> {
    let stdin = io::stdin();
    let mut lines = stdin.lock().lines();
    let n: usize = match lines.next() {
        Some(l) => l?.trim().parse().unwrap_or(128),
        None => return Ok(()),
    };
    let out = io::stdout();
    let mut w = BufWriter::new(out.lock());
    let mut cur: Option<Vec<String>> = None;
    let mut flush = |doc: Vec<String>, w: &mut BufWriter<_>| -> io::Result<()> {
        let sig = signature(&doc, n);
        let s: Vec<String> = sig.iter().map(|v| v.to_string()).collect();
        writeln!(w, "{}", s.join(" "))
    };
    for line in lines {
        let line = line?;
        if line == "#DOC" {
            if let Some(doc) = cur.take() {
                flush(doc, &mut w)?;
            }
            cur = Some(Vec::new());
        } else if let Some(doc) = cur.as_mut() {
            doc.push(line);
        }
    }
    if let Some(doc) = cur.take() {
        flush(doc, &mut w)?;
    }
    w.flush()
}
