import hashlib
import hmac
import uuid
from google.appengine.ext import ndb


class Uporabnik(ndb.Model):
    ime = ndb.StringProperty()
    priimek = ndb.StringProperty()
    email = ndb.StringProperty()
    sifrirano_geslo = ndb.StringProperty()

    @classmethod
    def ustvari(cls, ime, priimek, email, original_geslo):
        uporabnik = cls(ime=ime, priimek=priimek, email=email, sifrirano_geslo=cls.sifriraj_geslo(original_geslo=original_geslo))
        uporabnik.put()
        return uporabnik

    @classmethod
    def sifriraj_geslo(cls, original_geslo):
        salt = uuid.uuid4().hex
        sifra = hmac.new(str(salt), str(original_geslo), hashlib.sha512).hexdigest()
        return "%s:%s" % (sifra, salt)

    @classmethod
    def preveri_geslo(cls, original_geslo, uporabnik):
        sifra, salt = uporabnik.sifrirano_geslo.split(":")
        preverba = hmac.new(str(salt), str(original_geslo), hashlib.sha512).hexdigest()

        if preverba == sifra:
            return True
        else:
            return False


class Sporocilo(ndb.Model):
    naslov_sporocila = ndb.StringProperty()
    vsebina_sporocila = ndb.StringProperty()
    id_posiljatelja = ndb.IntegerProperty()
    id_prejemnika = ndb.IntegerProperty()
    datum = ndb.DateTimeProperty(auto_now_add=True)