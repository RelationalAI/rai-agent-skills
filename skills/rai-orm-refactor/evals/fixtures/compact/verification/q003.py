"""Synthetic saved scaffold, not an executable query."""
model.where(Case.is_closed(), Record.has_detail(RecordDetail)).select(Record.id)
