"""File token counting and analysis for LLM processing optimization."""

import re
from dataclasses import dataclass

from ..utils import token_utils
from ..utils.token_utils import ClaudeTokenCounter, ClaudeConfig
from ..utils import common_utils as utils
from ..types.source_format import SourceFormat


@dataclass
class FileTokenMetadata:
    """Data class for storing metadata of a file with token counts."""

    input_file_number: int | None
    input_file_path: str
    input_file_encoding: str
    input_file_content: str
    input_file_content_preprocessed: str
    input_file_token_count: int
    input_file_token_count_preprocessed: int  # pylint: disable=invalid-name
    tokenizer_type: str
    tokenizer_model: str


class FileTokenCountHelper:
    def __init__(self, endpoint_name: str = None, tokenizer_type: str = None, tokenizer_model: str = None):
        """
        Initialize the FileTokenCounter with endpoint name or explicit tokenizer settings.

        Args:
            endpoint_name (str, optional): The name of the endpoint to determine the tokenizer type.
                                         Used to infer tokenizer type and model if not explicitly provided.
            tokenizer_type (str, optional): The type of tokenizer to use ('openai' or 'claude').
                                          If not provided, will be inferred from endpoint_name.
            tokenizer_model (str, optional): The specific model to use for tokenization.
                                           If not provided, will be inferred from tokenizer_type or endpoint_name.
        """
        self.endpoint_name = endpoint_name

        # Use explicit tokenizer settings if provided
        if tokenizer_type:
            self.token_counter = token_utils.create_tokenizer_explicit(tokenizer_type, tokenizer_model or "")
        # Otherwise infer from endpoint_name
        elif endpoint_name:
            self.token_counter = token_utils.create_tokenizer_from_endpoint(endpoint_name)
        # Default to Claude if neither is provided
        else:
            self.token_counter = ClaudeTokenCounter(ClaudeConfig())

        # Get tokenizer information
        self.tokenizer_type, self.tokenizer_model = self.token_counter.get_type_info()

    def process_directory(
        self, input_dir: str, file_encoding: str | None = None, source_format: SourceFormat = SourceFormat.SQL
    ) -> list[FileTokenMetadata]:
        """
        Process all files in a directory and return a list of FileTokenMetadata objects with file details.

        Args:
            input_dir (str): The directory/pattern containing the files to be processed. Can be:
                - Single directory: "/path/to/dir"
                - Multiple directories: "/dir1,/dir2,/dir3"
                - Glob pattern: "/path/*/sql/*.sql"
                - Mixed: "/dir1,/path/*/sql,/dir3/**/*.sql"
            file_encoding (str | None): The encoding to use for reading the files. If not specified, the encoding is automatically detected using chardet.detect.
            source_format (SourceFormat): Source file format type. If SourceFormat.SQL, SQL comments will be removed for token counting.

        Returns:
            list[FileTokenMetadata]: A list of metadata objects for each processed file.
        """
        results = []
        for i, file_path in enumerate(utils.expand_input_paths(input_dir), start=1):
            sql_file_token_metadata = self.process_file(
                input_file_path=file_path, input_file_number=i, file_encoding=file_encoding, source_format=source_format
            )
            results.append(sql_file_token_metadata)
        return results

    def process_file(
        self,
        input_file_path: str,
        input_file_number: int | None = None,
        file_encoding: str | None = None,
        source_format: SourceFormat = SourceFormat.SQL,
    ) -> FileTokenMetadata:
        """
        Process a file and return its details including token counts.

        Args:
            input_file_path (str): The path of the file to be processed.
            input_file_number (int | None): The number of the input file. If not provided, it will be generated automatically.
            file_encoding (str | None): The encoding to use for reading the file. If not specified, the encoding is automatically detected using chardet.detect.
            source_format (SourceFormat): Source file format type. If SourceFormat.SQL, SQL comments will be removed for token counting.

        Returns:
            FileTokenMetadata: Metadata object containing file details and token counts.
        """
        content, input_file_encoding = utils.get_file_content(input_file_path, encoding=file_encoding)
        token_count = self.token_counter.count_tokens(content)

        content_preprocessed = None
        token_count_preprocessed = None

        if source_format == SourceFormat.SQL:
            content_preprocessed = utils.remove_sql_comments(content)
            content_preprocessed = re.sub(r'\s+', ' ', content_preprocessed)
            token_count_preprocessed = self.token_counter.count_tokens(content_preprocessed)
        else:
            # For generic files, use original content (no preprocessing)
            content_preprocessed = content
            token_count_preprocessed = token_count

        return FileTokenMetadata(
            input_file_number=input_file_number,
            input_file_path=input_file_path,
            input_file_encoding=input_file_encoding,
            tokenizer_type=self.tokenizer_type,
            tokenizer_model=self.tokenizer_model,
            input_file_token_count=token_count,
            input_file_token_count_preprocessed=token_count_preprocessed,
            input_file_content=content,
            input_file_content_preprocessed=content_preprocessed,
        )
