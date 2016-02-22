# encoding: utf-8
import os
import mock
import sys
import requests

test_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(test_dir, os.path.pardir))
os.environ["DJANGO_SETTINGS_MODULE"] = 'tests.settings'

import django
from django.test import TestCase
from django.core.management import call_command
from django.core.exceptions import ValidationError
django.setup()
call_command('migrate', '--run-syncdb')

from cep.models import Cep
from cep.forms import CepField
from cep.parser import Parser


class FakeRequest(object):
    def __init__(self, content):
        self.content = content


class FakeException(requests.RequestException):
    pass


def fake_request_success_brasilia(*args, **kwargs):
    with open('tests/responses/success.html', 'r') as f:
        return FakeRequest(f.read())


def fake_request_success_logradouro(*args, **kwargs):
    with open('tests/responses/success-logradouro.html', 'r') as f:
        return FakeRequest(f.read())


def fake_request_fail(*args, **kwargs):
    with open('tests/responses/error.html', 'r') as f:
        return FakeRequest(f.read())


def fake_request_error(*args, **kwargs):
    raise FakeException('Internet Down')


class CepModelTestCase(TestCase):
    def test_can_isntantiate(self):
        cep = Cep(codigo='11111111')
        cep.save()
        self.assertIsInstance(cep, Cep)

    def test_sucessive_saves_increments_id(self):
        cep = Cep(codigo='11111111')
        cep.save()
        novo_cep = Cep(codigo='11111112')
        novo_cep.save()
        self.assertEqual(2, novo_cep.id)


class CepFormTestCase(TestCase):
    def test_invalid_cep_format(self):
        field = CepField()
        with self.assertRaises(ValidationError):
            field.clean('701150-903')

    @mock.patch('requests.post', mock.Mock(side_effect=fake_request_fail))
    def test_validate_with_correios_invalid_cep(self):
        field = CepField()
        with self.assertRaises(ValidationError):
            field.clean('71150-903')

    @mock.patch('requests.post', mock.Mock(side_effect=fake_request_success_brasilia))
    def test_correctly_cep(self):
        field = CepField()
        self.assertEqual('70.150-903', field.clean('70.150-903'))

    @mock.patch('requests.post', mock.Mock(side_effect=fake_request_error))
    def test_validate_without_internet_silent(self):
        field = CepField(should_raise_exception=False)
        self.assertEqual('70.150-903', field.clean('70.150-903'))

    @mock.patch('requests.post', mock.Mock(side_effect=fake_request_error))
    def test_validate_without_internet_raises_exception(self):
        field = CepField()
        with self.assertRaises(ValidationError):
            field.clean('70.150-903')

    @mock.patch('requests.post',
                mock.Mock(side_effect=iter(fake_request_success_brasilia, fake_request_error)))
    def test_revalidate_saved_cep(self):
        field = CepField()
        field.clean('70.150-903')
        self.assertEqual('70.150-903', field.clean('70.150-903'))

    @mock.patch('requests.post', mock.Mock(side_effect=fake_request_success_brasilia))
    def test_validate_fulfill_module(self):
        field = CepField()
        field.clean('70.150-903')
        cep = Cep.objects.first()
        self.assertEqual(u'Zona Cívico-Administrativa', cep.bairro)

    @mock.patch('requests.post', mock.Mock(side_effect=fake_request_success_brasilia))
    def test_validate_fulfill_module_logradouro_with_client(self):
        field = CepField()
        field.clean('70.150-903')
        cep = Cep.objects.first()
        self.assertEqual(u'Palácio da Alvorada (Residência Oficial do Presidente da República)',
                         cep.logradouro)

    @mock.patch('requests.post', mock.Mock(side_effect=fake_request_success_logradouro))
    def test_validate_fulfill_module_logradouro_without_client(self):
        field = CepField()
        field.clean('70.150-903')
        cep = Cep.objects.first()
        self.assertEqual(u'Rua Doutor Raul Silva',
                         cep.logradouro)

    @mock.patch('requests.post', mock.Mock(side_effect=fake_request_success_logradouro))
    def test_validate_fulfill_module_logradouro_with_complemento(self):
        field = CepField()
        field.clean('70.150-903')
        cep = Cep.objects.first()
        self.assertEqual(u'de 2301/2302 ao fim',
                         cep.complemento)


class ParserTestCase(TestCase):
    def setUp(self):
        self.data = {
            'logradouro': 'Rua Doutor Raul Silva',
            'bairro': 'Jardim Francisco Fernandes',
            'cidade': u'São José do Rio Preto',
            'estado': 'SP',
            'complemento': 'de 2301/2302 ao fim',
        }

    def test_parser_gets_bairro(self):
        response = fake_request_success_logradouro()
        parser = Parser(response.content)
        parsed_data = parser.get_data()
        self.assertEqual(self.data['bairro'],
                         parsed_data['bairro'])

    def test_parser_gets_cidade(self):
        response = fake_request_success_logradouro()
        parser = Parser(response.content)
        parsed_data = parser.get_data()
        self.assertEqual(self.data['cidade'],
                         parsed_data['cidade'])

    def test_parser_gets_bairro_com_acento(self):
        data = {
            'logradouro': 'SPP',
            'bairro': u'Zona Cívico-Administrativa',
            'cidade': u'Brasília',
            'estado': 'DF',
        }
        response = fake_request_success_brasilia()
        parser = Parser(response.content)
        parsed_data = parser.get_data()
        self.assertEqual(data['cidade'],
                         parsed_data['cidade'])

    def test_parser_gets_estado(self):
        response = fake_request_success_logradouro()
        parser = Parser(response.content)
        parsed_data = parser.get_data()
        self.assertEqual(self.data['estado'],
                         parsed_data['estado'])

    def test_parser_gets_logradouro(self):
        response = fake_request_success_logradouro()
        parser = Parser(response.content)
        parsed_data = parser.get_data()
        self.assertEqual(self.data['logradouro'],
                         parsed_data['logradouro'])

    def test_parser_gets_complemento(self):
        response = fake_request_success_logradouro()
        parser = Parser(response.content)
        parsed_data = parser.get_data()
        self.assertEqual(self.data['complemento'],
                         parsed_data['complemento'])
