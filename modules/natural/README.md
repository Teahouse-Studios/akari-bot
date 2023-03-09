## Files

-   `datasets/`: for dataset archive.
-   Run `create_jsonl.py` to create jsonl files for dataset.txt
-   dataset.txt is the training-pending dataset
-   I regularly run a new fine-tuning job on the dataset.txt. After the job is done, I will move the dataset to `datasets/` and remove it from `dataset.txt`.

The latest model is `curie:ft-teahouse-studios:nl2c-2023-03-09-11-31-56`.
