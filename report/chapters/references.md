# REFERENCES

## Research Papers (verified via original source/abstract before inclusion — see report/BLUEPRINT.md)

1. Zhou, Y., Liu, S., Siow, J., Du, X., & Liu, Y. (2019). Devign: Effective Vulnerability
   Identification by Learning Comprehensive Program Semantics via Graph Neural Networks. *Advances in
   Neural Information Processing Systems (NeurIPS) 32*.

2. Feng, Z., Guo, D., Tang, D., Duan, N., Feng, X., Gong, M., Shou, L., Qin, B., Liu, T., Jiang, D., &
   Zhou, M. (2020). CodeBERT: A Pre-Trained Model for Programming and Natural Languages. *Findings of
   the Association for Computational Linguistics: EMNLP 2020*.

3. Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). BERT: Pre-training of Deep Bidirectional
   Transformers for Language Understanding. *Proceedings of NAACL-HLT 2019*.

4. Li, Z., Zou, D., Xu, S., Ou, X., Jin, H., Wang, S., Deng, Z., & Zhong, Y. (2018). VulDeePecker: A
   Deep Learning-Based System for Vulnerability Detection. *Network and Distributed System Security
   Symposium (NDSS) 2018*.

5. Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. *Proceedings of the 22nd
   ACM SIGKDD International Conference on Knowledge Discovery and Data Mining (KDD 2016)*.

6. Breiman, L. (2001). Random Forests. *Machine Learning*, 45(1), 5–32.

7. McCabe, T. J. (1976). A Complexity Measure. *IEEE Transactions on Software Engineering*, SE-2(4),
   308–320.

8. Chidamber, S. R., & Kemerer, C. F. (1994). A Metrics Suite for Object Oriented Design. *IEEE
   Transactions on Software Engineering*, 20(6), 476–493.

9. Lu, S., Guo, D., Ren, S., Huang, J., Svyatkovskiy, A., Blanco, A., Clement, C., Drain, D., Jiang, D.,
   Tang, D., Li, G., Zhou, L., Shou, L., Zhou, L., Tufano, M., Gong, M., Zhou, M., Duan, N., Sundaresan,
   N., Deng, S. K., Fu, S., & Liu, S. (2021). CodeXGLUE: A Machine Learning Benchmark Dataset for Code
   Understanding and Generation. *Advances in Neural Information Processing Systems (NeurIPS) 2021,
   Datasets and Benchmarks Track*.

10. Chakraborty, S., Krishna, R., Ding, Y., & Ray, B. (2020). Deep Learning based Vulnerability
    Detection: Are We There Yet? *arXiv:2009.07235* (later published in *IEEE Transactions on Software
    Engineering*, 2021).

11. Fu, M., & Tantithamthavorn, C. (2022). LineVul: A Transformer-based Line-Level Vulnerability
    Prediction. *Proceedings of the 19th International Conference on Mining Software Repositories
    (MSR 2022)*.

12. Bessey, A., Block, K., Chelf, B., Chou, A., Fulton, B., Hallem, S., Henri-Gros, C., Kamsky, A.,
    McPeak, S., & Engler, D. (2010). A Few Billion Lines of Code Later: Using Static Analysis to Find
    Bugs in the Real World. *Communications of the ACM*, 53(2), 66–75.

## Datasets and Tools

- Devign dataset — function-level, C-language vulnerability-labeled dataset drawn from the FFmpeg and
  QEMU open-source projects, introduced in Zhou et al. (2019) above.
- tree-sitter and tree-sitter-c — incremental parser generator and C grammar, used for AST extraction
  (https://tree-sitter.github.io/tree-sitter/).
- Hugging Face Transformers — `microsoft/codebert-base` pretrained checkpoint, used for semantic
  embedding extraction.

## Frameworks and APIs Used

- FastAPI (https://fastapi.tiangolo.com/) — backend web framework.
- React, Vite, TypeScript, Tailwind CSS, Recharts, @xyflow/react, Monaco Editor — frontend stack
  (Chapter 1.6.1 lists exact pinned versions from the project's own `package.json`/`requirements.txt`).
- SQLAlchemy — ORM used for the local SQLite persistence layer.
- Docker / Docker Compose — containerized deployment.
- GitHub Actions — CI/CD pipeline.

## Project's Own Internal Documentation (primary sources verified and cited throughout this report)

- `models/training_metadata.json`, `models/ml_baseline_status.json` — ground-truth trained-model
  metrics, cited throughout Chapters 3, 6, and 7.
- `docs/ML_FORENSIC_AUDIT_PHASE4.md`, `docs/ML_ALIGNMENT_FIX_RESULTS.md` — the feature-fusion
  alignment defect and its correction, Chapter 3.4.4/7.3.
- `docs/MODALITY_ABLATION_RESULTS.md` — the modality-ablation experiment, Chapters 3.4.3 and 7.2.3.
- `docs/ML_IMPROVEMENT_PLAN.md` — future-work items reused in Chapter 8.3.
- `paper/research_paper.md` — the CodeBERT embedding-anisotropy diagnostic reused in Chapter 8.2.

[REQUIRES VERIFICATION before final submission]: confirm university-required citation style
(APA/IEEE/other) from any style guidance elsewhere in the department's submission instructions not
contained in the format template itself, and reformat the list above accordingly if it differs from the
numbered style used here.
