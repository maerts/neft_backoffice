# NEFT Backoffice Integration for Home Assistant

This custom integration allows you to monitor your NEFT electric vehicle charging transactions and tariffs in Home Assistant.

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Search for "NEFT Backoffice" in HACS
3. Click Install
4. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/neft_backoffice` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Search for "NEFT Backoffice"
4. Enter your NEFT Backoffice credentials
5. Configure the update interval (optional)

## Sensors

The integration creates the following sensors:

### Transaction Sensors
- **Total Transactions**: Total number of stored transactions
- **New Transactions**: Number of new transactions since last update (with transaction details in attributes)
- **Total Cost**: Sum of all transaction costs (EUR)
- **Total Energy Consumption**: Sum of all energy consumed (kWh)

### Tariff Sensors
- **AC Charging Tariff**: Current AC charging tariff (per kWh as main state)
  - Attributes: per kWh, per session, per hour tariffs
- **DC Charging Tariff**: Current DC charging tariff (per kWh as main state)
  - Attributes: per kWh, per session, per hour tariffs

## Services

### `neft_backoffice.refresh_data`
Manually refresh transaction and tariff data.

## Example Automations

### Notify on New Transactions

```yaml
automation:
  - alias: "Notify on new NEFT transactions"
    trigger:
      - platform: state
        entity_id: sensor.neft_backoffice_new_transactions
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state | int > 0 }}"
    action:
      - service: notify.mobile_app
        data:
          title: "New Charging Transactions"
          message: >
            {{ trigger.to_state.state }} new transaction(s) detected.
            Total cost: {{ state_attr('sensor.neft_backoffice_new_transactions', 'transactions')[0].cost }}

