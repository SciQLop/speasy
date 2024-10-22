from typing import Protocol, Optional, List, AnyStr, Mapping, Union
import io
from speasy.products import SpeasyVariable


Buffer = Union[memoryview, bytearray, bytes]

class CodecInterface(Protocol):
    """Interface for codecs.

    Codecs are used to load and save data from different formats. Codecs must implement this interface to be registered in the codecs registry.
    """

    def load_variables(self, variables: List[AnyStr], file: Union[Buffer, str, io.IOBase], cache_remote_files=True,
                       **kwargs) -> Optional[Mapping[AnyStr, SpeasyVariable]]:
        """Load variables from a file. The file can be a local file, a remote file or a file-like object.

        Parameters
        ----------
        variables : List[str]
            List of variable names to load
        file : Buffer or str or io.IOBase
            File to load variables from
        cache_remote_files : bool
            Whether to cache remote files
        kwargs
            Additional keyword arguments, codec specific arguments

        Returns
        -------
        Optional[Mapping[str, SpeasyVariable]]
            A dictionary with the variables loaded

        Raises
        ------
        NotImplementedError
            If the method is not implemented

        See Also
        --------
        load_variable, save_variables

        """
        ...

    def load_variable(self, variable: AnyStr, file: Union[Buffer, str, io.IOBase], cache_remote_files=True, **kwargs) -> \
    Optional[SpeasyVariable]:
        """Load a variable from a file. The file can be a local file, a remote file or a file-like object.

        Parameters
        ----------
        variable : str
            Variable name to load
        file : Buffer or str or io.IOBase
            File to load variable from
        cache_remote_files : bool
            Whether to cache remote files
        kwargs
            Additional keyword arguments, codec specific arguments

        Returns
        -------
        Optional[SpeasyVariable]
            The variable loaded

        Raises
        ------
        NotImplementedError
            If the method is not implemented

        See Also
        --------
        load_variables, save_variables

        """
        ...

    def save_variables(self, variables: List[SpeasyVariable], file: Optional[Union[str, io.IOBase]]=None, **kwargs) -> Union[bool,Buffer]:
        """Save variables to a file. The file can be a local file, a remote file or a file-like object.

        Parameters
        ----------
        variables : List[SpeasyVariable]
            List of variables to save
        file : str or io.IOBase
            File to save variables to, if None, return the data as bytes
        kwargs
            Additional keyword arguments, codec specific arguments

        Returns
        -------
        Union[bool, Buffer]
            True if the variables were saved successfully, the data as buffer compatible object if file is None

        Raises
        ------
        NotImplementedError
            If the method is not implemented which is an acceptable behavior for read-only codecs

        See Also
        --------
        load_variables, load_variable

        """
        ...

    @property
    def supported_extensions(self) -> List[str]:
        """List of supported file extensions, without the dot. Do return extensions that could be ambiguous with other codecs."""
        ...

    @property
    def supported_mimetypes(self) -> List[str]:
        """List of supported mime types."""
        ...

    @property
    def name(self) -> str:
        """Codec name. Must be unique."""
        ...
