"""Synthetic saved scaffold, not an executable query."""
model.where(SelectedAsset, Asset).select(SelectedAsset.cost, Asset.label)
