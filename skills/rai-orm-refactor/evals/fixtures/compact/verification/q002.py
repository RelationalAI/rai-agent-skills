"""Synthetic saved scaffold, not an executable query."""
model.where(Asset, Case.is_active(), Record.has_detail(RecordDetail)).select(Asset.cost)
