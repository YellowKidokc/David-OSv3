# Master Equation Namer

Prediction_GUI registers this as App 160, embedded and pending extraction.

1. FIS reads a local sample and scores ten factors independently using the factor keyword lists. Zero hits scores 0, one or two scores 1, three to five scores 2, and six or more scores 3.
2. The full profile prints the scores in order and appends the five configured pairs. The factors are Grace (G), Moral Alignment (M), Truth Signal (E), Entropy (S), Time/Kairos (T), Knowledge/Logos (K), Relational Frame (R), Quantum Uncertainty (Q), Faith/Fruit (F), and Christ/Coherence (C).
3. The short profile omits zero factors and includes a pair if either member scored above zero. Treat these pair labels as template metadata. An all-zero profile displays as UNSCORED.
4. The folder aggregate averages each factor across files with at least one score. For a matching Master Equation folder, the heading may use a local declaration or a labeled hard-coded R3 fallback. Use the source label to tell where the heading came from.

    Full   G3 M0 E0 S1 T0 K0 R0 Q0 F0 C2 :: [G.C] [M.F] [E.Q] [S.R] [T.K]
    Short  G3 S1 C2 :: [G.C] [S.R]

The MEQ__title__date address is a separate keyword-triggered proposal using the modification date. The file renamer has a separate filename grammar. For an ORBITS action, cite the operation ID such as GRACE-001 / G — Restore alongside the document's χ profile when both are needed.

- [Classifier](../../file-intelligence-system/fis_classifier.py)
- [χ formatter, folder aggregation, and declaration reader](../../file-intelligence-system/fis_folder_memory.py)
- [Address and filename proposals](../../apps/classify/src/engines/fis/fis_namer.py)
- [Prediction_GUI app registry](D:/GitHub/Prediction_GUI/apps/registry.json)
