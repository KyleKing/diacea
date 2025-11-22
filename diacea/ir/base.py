"""Base classes for parsers and generators.

Defines the interface that all format parsers and generators must implement.
"""

from abc import ABC, abstractmethod
from typing import Any

from .elements import Diagram


class Parser(ABC):
    """Base class for format parsers.

    A parser converts a format-specific representation into the universal IR.
    """

    @abstractmethod
    def parse(self, data: Any) -> Diagram:
        """Parse format-specific data to IR Diagram.

        Args:
            data: Format-specific input data (dict, string, etc.)

        Returns:
            Diagram object in IR format

        Raises:
            ValueError: If data is invalid or cannot be parsed
        """
        pass


class Generator(ABC):
    """Base class for format generators.

    A generator converts the universal IR into a format-specific representation.
    """

    @abstractmethod
    def generate(self, diagram: Diagram) -> str:
        """Generate format-specific output from IR Diagram.

        Args:
            diagram: Diagram object in IR format

        Returns:
            Format-specific output as string

        Raises:
            ValueError: If diagram cannot be converted to this format
        """
        pass
