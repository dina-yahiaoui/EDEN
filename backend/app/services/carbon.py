def get_emission_factor(energy_type: str) -> float:
    """
    Retourne un facteur d'émission simple pour le MVP.
    Valeurs indicatives en kgCO2e / kWh.
    À remplacer ensuite par les facteurs ADEME.
    """

    factors = {
        "electricity": 0.056,
        "gas": 0.204,
    }

    return factors.get(energy_type, 0.0)


def calculate_carbon_emissions(invoice_data: dict) -> dict:
    """
    Calcule les émissions CO2e à partir de la consommation extraite.
    """

    energy_type = invoice_data.get("energy_type", "")
    consumption_kwh = invoice_data.get("consumption_kwh", 0.0)

    emission_factor = get_emission_factor(energy_type)
    emissions_kgco2e = consumption_kwh * emission_factor

    return {
        "energy_type": energy_type,
        "consumption_kwh": consumption_kwh,
        "emission_factor_kgco2e_per_kwh": emission_factor,
        "emissions_kgco2e": round(emissions_kgco2e, 2),
    }