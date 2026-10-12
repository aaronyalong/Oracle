---
tags: [ai, evaluation]
---
# Cross-Validation

Cross-validation estimates how well a model generalizes by training and testing on different splits of the data.

## k-fold
Split the data into k folds (usually 5 or 10). Train on k−1 folds, test on the remaining one, and repeat so every fold is the test set once. Report the average score.

## Stratified k-fold
Keeps the class proportions the same in every fold. Use it for imbalanced classification.

## Data leakage
Any preprocessing fitted on the whole dataset (scaling, feature selection) leaks test information into training. Fit preprocessing inside each fold.

Used to tune [[Regularization]] strength.
