from rolepermissions.roles import AbstractUserRole


class Admin(AbstractUserRole):
    available_permissions = {
        'manage_users': True,
        'manage_shipments': True,
        'manage_payments': True,
    }


class Driver(AbstractUserRole):
    available_permissions = {
        'accept_shipment': True,
        'update_location': True,
    }


class Customer(AbstractUserRole):
    available_permissions = {
        'create_shipment': True,
        'track_shipment': True,
    }