from adaptexts.adapters.interface import AdapterInterface
from adaptexts.adapters.mixins import FileTreeMixin, IterationMixin


class DirectoryAdapter(FileTreeMixin, IterationMixin, AdapterInterface):
    pass
