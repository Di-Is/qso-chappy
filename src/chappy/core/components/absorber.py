"""Absorber component for modeling absorption lines."""

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

from chappy.core.change_set import ChangeSet
from chappy.core.math import calculate_absorption_profile
from chappy.core.settings import is_verbose

from .base import ModelComponent, Parameter

if TYPE_CHECKING:
    from chappy.core.atomic_data import AtomicLine

    from .tie_set import ParameterTieSet


class AbsorberComponent(ModelComponent):
    """Component for modeling absorption lines using Voigt profiles.

    This component models absorption lines in astronomical spectra using
    Voigt profiles, which account for both thermal (Doppler) broadening
    and natural/collisional broadening.

    Parameters:
        wavelength: Rest wavelength of the transition (Angstroms)
        column_density: Log10 of column density (cm⁻²)
        b_parameter: Doppler b parameter (km/s)
        redshift: Redshift of the absorber
        oscillator_strength: Oscillator strength of the transition
        gamma: Natural broadening parameter (s⁻¹)
    """

    def __init__(  # noqa: PLR0913 # All parameters are essential physical properties for absorption line modeling
        self,
        name: str = "Absorber",
        wavelength: float = 5000.0,
        column_density: float = 14.0,
        b_parameter: float = 10.0,
        redshift: float = 0.0,
        oscillator_strength: float = 0.4164,  # Lyman alpha default
        gamma: float = 6.265e8,  # Lyman alpha default
        component_id: str | None = None,
        group_id: str | None = None,
    ) -> None:
        """Initialize absorber component.

        Args:
            name: Component name
            wavelength: Rest wavelength in Angstroms
            column_density: Log10 column density
            b_parameter: Doppler parameter in km/s
            redshift: Redshift
            oscillator_strength: Oscillator strength
            gamma: Natural broadening in s⁻¹
            component_id: Unique identifier for the component (generated if not provided)
            group_id: Optional structure region identifier
        """
        super().__init__(name, component_id)

        # Define fitting parameters
        self.parameters = {
            "column_density": Parameter(
                "column_density", column_density, min_val=10.0, max_val=22.0, unit="log(cm⁻²)"
            ),
            "b_parameter": Parameter(
                "b_parameter", b_parameter, min_val=1.0, max_val=1000.0, unit="km/s"
            ),
            "redshift": Parameter("redshift", redshift, min_val=-0.1, max_val=10.0, unit=""),
            "covering_factor": Parameter(
                "covering_factor", 1.0, min_val=0.0, max_val=1.0, fixed=True, unit=""
            ),
        }

        # Fixed atomic parameters (not fitted)
        self.wavelength = wavelength
        self.oscillator_strength = oscillator_strength
        self.gamma = gamma

        # Parameter tie set support
        self.tie_set: ParameterTieSet | None = None
        self.atomic_line: AtomicLine | None = None

        # External continuum support for absorption mode
        self.external_continuum_name: str | None = None
        self._cached_continuum_flux: NDArray[np.float64] | None = None
        self._cached_continuum_wavelength: NDArray[np.float64] | None = None

        # Structure region association
        self.group_id: str | None = group_id

    def calculate(self, wavelength: NDArray[np.float64]) -> NDArray[np.float64]:
        """Calculate absorption profile.

        Args:
            wavelength: Wavelength array in Angstroms

        Returns:
            Transmission array (0 = complete absorption, 1 = no absorption)
        """
        # Get parameter values
        lambda0 = self.wavelength
        log_n = self.parameters["column_density"].value
        b = self.parameters["b_parameter"].value
        z = self.parameters["redshift"].value
        covering_factor = float(self.parameters["covering_factor"].value)
        if not 0.0 <= covering_factor <= 1.0:
            msg = f"Invalid covering_factor for absorber {self.id}: {covering_factor}"
            raise ValueError(msg)

        # Debug logging
        logger = logging.getLogger(__name__)
        if is_verbose():
            logger.info(
                "Voigt profile for %s: λ=%.1fÅ, z=%.4f, logN=%.1f, b=%.1f km/s, f=%.4f",
                self.name,
                lambda0,
                z,
                log_n,
                b,
                self.oscillator_strength,
            )

        # Calculate observed wavelength for debug info
        lambda_obs = lambda0 * (1.0 + z)

        # Use shared calculation function
        transmission = calculate_absorption_profile(
            wavelength, z, log_n, b, lambda0, self.oscillator_strength, self.gamma
        )

        # Apply external continuum normalization if available
        if (
            self.external_continuum_name
            and self._cached_continuum_flux is not None
            and self._cached_continuum_wavelength is not None
            and len(wavelength) == len(self._cached_continuum_wavelength)
            and np.allclose(wavelength, self._cached_continuum_wavelength)
        ):
            # Apply continuum normalization
            # The transmission represents absorption against the continuum
            # If continuum != 1.0, the effective absorption depth changes
            continuum_flux = self._cached_continuum_flux
            # Avoid division by zero
            continuum_flux = np.where(continuum_flux <= 0, 1.0, continuum_flux)

            # Simple approach: scale absorption depth by continuum level
            # When continuum > 1.0, absorption appears relatively shallower
            # When continuum < 1.0, absorption appears relatively deeper
            absorption_depth = 1.0 - transmission  # Convert to absorption depth
            scaled_depth = absorption_depth / continuum_flux  # Scale by continuum
            transmission = 1.0 - scaled_depth  # Convert back to transmission

            # Ensure transmission stays in valid range [0, 1]
            transmission = np.clip(transmission, 0.0, 1.0)
            if is_verbose():
                logger.info(
                    "Applied external continuum '%s' to absorption profile. Continuum range: %.3f - %.3f",
                    self.external_continuum_name,
                    np.min(continuum_flux),
                    np.max(continuum_flux),
                )

        # Apply covering factor (partial covering model)
        if covering_factor != 1.0:
            transmission = covering_factor * transmission + (1.0 - covering_factor)

        # Debug info about the result
        if is_verbose():
            min_transmission = np.min(transmission)
            center_idx = np.argmin(np.abs(wavelength - lambda_obs))
            if 0 <= center_idx < len(transmission):
                logger.info(
                    "Profile calculated for %s: min transmission = %.4f",
                    self.name,
                    min_transmission,
                )
            else:
                logger.info(
                    "Profile calculated for %s: min transmission = %.4f (center outside range)",
                    self.name,
                    min_transmission,
                )

        return transmission

    def has_active_external_continuum(self) -> bool:
        """Whether an external continuum is bound (only valid on the observed grid)."""
        return bool(self.external_continuum_name) and self._cached_continuum_flux is not None

    def set_group(self, group_id: str | None) -> ChangeSet:
        """Assign the absorber to an absorption-region identifier."""
        if self.group_id == group_id:
            return ChangeSet.empty()
        self.group_id = group_id
        return self.notify_changed()

    @classmethod
    def from_atomic_line(
        cls, atomic_line: "AtomicLine", name: str | None = None, **kwargs: float
    ) -> "AbsorberComponent":
        """Create AbsorberComponent from AtomicLine data.

        Args:
            atomic_line: AtomicLine data
            name: Component name (auto-generated if None)
            **kwargs: Override default parameters

        Returns:
            Configured AbsorberComponent
        """
        component_name = name or f"{atomic_line.species} {atomic_line.wavelength_angstrom:.1f}"

        # Extract known parameters from kwargs
        column_density = kwargs.pop("column_density", 14.0)
        b_parameter = kwargs.pop("b_parameter", 10.0)
        redshift = kwargs.pop("redshift", 0.0)
        component_id_raw = kwargs.pop("component_id", None)
        # Ensure component_id is a string or None
        component_id = str(component_id_raw) if component_id_raw is not None else None

        component = cls(
            name=component_name,
            wavelength=atomic_line.wavelength_angstrom,
            oscillator_strength=atomic_line.oscillator_strength,
            gamma=atomic_line.gamma_value,
            column_density=column_density,
            b_parameter=b_parameter,
            redshift=redshift,
            component_id=component_id,
        )

        # Store reference to atomic line data
        component.atomic_line = atomic_line

        return component

    def set_parameter(self, name: str, value: float) -> ChangeSet:
        """Set parameter value with multiplet synchronization.

        Args:
            name: Parameter name
            value: New value

        Raises:
            KeyError: If parameter not found
        """
        if name not in self.parameters:
            msg = f"Parameter '{name}' not found in {self.name}"
            raise KeyError(msg)

        # If part of a tie set and parameter is shared, sync with the tie set
        if self.tie_set is not None and name in self.tie_set.mask:
            # Update master parameter in the tie set
            return self.tie_set.set_shared_parameter(name, value)
        # Normal parameter update
        self.parameters[name].set_value(value)
        return self.notify_changed()

    def set_external_continuum(
        self,
        continuum_name: str | None,
        wavelength: NDArray[np.float64] | None = None,
        continuum_flux: NDArray[np.float64] | None = None,
    ) -> ChangeSet:
        """Set external continuum for this absorber.

        Args:
            continuum_name: Name of the continuum component (None to clear)
            wavelength: Wavelength array for continuum interpolation
            continuum_flux: Continuum flux array
        """
        self.external_continuum_name = continuum_name

        if continuum_name is None:
            # Clear cached continuum
            self._cached_continuum_flux = None
            self._cached_continuum_wavelength = None
            logger = logging.getLogger(__name__)
            logger.info("Cleared external continuum for absorber '%s'", self.name)
        # Cache continuum data
        elif wavelength is not None and continuum_flux is not None:
            self._cached_continuum_wavelength = wavelength.copy()
            self._cached_continuum_flux = continuum_flux.copy()
            logger = logging.getLogger(__name__)
            logger.info("Set external continuum '%s' for absorber '%s'", continuum_name, self.name)
        else:
            logger = logging.getLogger(__name__)
            logger.warning(
                "External continuum '%s' set but no data provided for '%s'",
                continuum_name,
                self.name,
            )

        return self.notify_changed()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AbsorberComponent":
        """Deserialize absorber component from a dictionary."""
        parameters_data = data.get("parameters", {})

        def _param_value(name: str, default: float) -> float:
            param_info = parameters_data.get(name)
            if isinstance(param_info, dict):
                return float(param_info.get("value", default))
            return float(default)

        component = cls(
            name=data.get("name", "Absorber"),
            wavelength=float(data.get("wavelength", 5000.0)),
            column_density=_param_value("column_density", 14.0),
            b_parameter=_param_value("b_parameter", 10.0),
            redshift=_param_value("redshift", 0.0),
            oscillator_strength=float(data.get("oscillator_strength", 0.4164)),
            gamma=float(data.get("gamma", 6.265e8)),
            component_id=data.get("id"),
            group_id=data.get("group_id"),
        )

        component.enabled = bool(data.get("enabled", True))
        component.external_continuum_name = data.get("external_continuum_name")

        for name, param_info in parameters_data.items():
            param_obj = component.parameters.get(name)
            if param_obj is None:
                component.parameters[name] = Parameter.from_dict(param_info)
                continue

            param_obj.min_val = float(param_info.get("min_val", param_obj.min_val))
            param_obj.max_val = float(param_info.get("max_val", param_obj.max_val))
            param_obj.fixed = bool(param_info.get("fixed", param_obj.fixed))
            param_obj.error = float(param_info.get("error", param_obj.error))
            param_obj.unit = param_info.get("unit", param_obj.unit)
            param_obj.set_value(float(param_info.get("value", param_obj.value)))

        return component
