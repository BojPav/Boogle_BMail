#!/usr/bin/env python
import os
import jinja2
import webapp2
import cgi
import datetime
import time
import hmac
import hashlib
import uuid
from secret import secret
from models import Uporabnik
from models import Sporocilo
from google.appengine.api import users
from google.appengine.api import urlfetch
import json

template_dir = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir), autoescape=False)


class BaseHandler(webapp2.RequestHandler):

    def write(self, *a, **kw):
        return self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        return self.write(self.render_str(template, **kw))

    def render_template(self, view_filename, params=None):
        if not params:
            params = {}

        cookie_value = self.request.cookies.get("uid")

        if cookie_value:
            params["logiran"] = self.preveri_cookie(cookie_vrednost=cookie_value)
        else:
            params["logiran"] = False

        template = jinja_env.get_template(view_filename)
        self.response.out.write(template.render(params))

    def ustvari_cookie(self, uporabnik):
        uporabnik_id = uporabnik.key.id()
        expires = datetime.datetime.utcnow() + datetime.timedelta(days=10)
        expires_ts = int(time.mktime(expires.timetuple()))
        sifra = hmac.new(str(uporabnik_id), str(secret) + str(expires_ts), hashlib.sha1).hexdigest()
        vrednost = "{0}:{1}:{2}".format(uporabnik_id, sifra, expires_ts)
        self.response.set_cookie(key="uid", value=vrednost, expires=expires)

    def preveri_cookie(self, cookie_vrednost):
        uporabnik_id, sifra, expires_ts = cookie_vrednost.split(":")

        if datetime.datetime.utcfromtimestamp(float(expires_ts)) > datetime.datetime.now():
            preverba = hmac.new(str(uporabnik_id), str(secret) + str(expires_ts), hashlib.sha1).hexdigest()

            if sifra == preverba:
                return True
            else:
                return False
        else:
            return False


class MainHandler(BaseHandler):
    def get(self):
        return self.render_template("hello.html")


class RegistracijaHandler(BaseHandler):
    def get(self):
        return self.render_template("registracija.html")

    def post(self):
        ime = self.request.get("ime")
        priimek = self.request.get("priimek")
        email = self.request.get("email")
        geslo = self.request.get("geslo")
        ponovno_geslo = self.request.get("ponovno_geslo")

        if geslo == ponovno_geslo:
            Uporabnik.ustvari(ime=ime, priimek=priimek, email=email, original_geslo=geslo)
            self.render_template("prejeto.html")
        else:
            return self.write("Wrong retyped password...")


class LoginHandler(BaseHandler):
    def get(self):
        return self.render_template("login.html")

    def post(self):
        email = self.request.get("email")
        geslo = self.request.get("geslo")

        uporabnik = Uporabnik.query(Uporabnik.email == email).get()

        if uporabnik:

            if Uporabnik.preveri_geslo(original_geslo=geslo, uporabnik=uporabnik):  # ce uporabnik obstaja redirecta na main page/prejeto
                self.ustvari_cookie(uporabnik=uporabnik)
                self.redirect("/prejeto")
            else:
                return self.write("Wrong password...go back and try again")
        else:
            return self.render_template("registracija.html")
        #if Uporabnik.preveri_geslo(original_geslo=geslo, uporabnik=uporabnik):
            #self.ustvari_cookie(uporabnik=uporabnik)
            #return self.render_template("prejeto.html")
        #else:
            #return self.write("Uporabnik ni logiran")


class PrejetoHandler(BaseHandler):
    def get(self):
        return self.render_template("prejeto.html")


class NovoSporociloHandler(BaseHandler):    # potrebno implementirati if v post za uporabnika ki ne obstaja
    def get(self):
        uporabnik = Uporabnik.query().fetch()
        params = {"ime_uporabnika": uporabnik}
        return self.render_template("novo_sporocilo.html", params=params)

    def post(self):
        cookie_value = self.request.cookies.get("uid")  # po cookie-u dobimo ID posiljatelja
        posiljatelj_id, _, _ = cookie_value.split(":")  # po cookie-u dobimo ID posiljatelja
        posiljatelj_id = int(posiljatelj_id)  # po cookie-u dobimo ID posiljatelja
        posiljatelj = Uporabnik.get_by_id(posiljatelj_id).ime  # po ID-ju dobimo ime posiljatelja !!!

        ime_uporabnika = self.request.get("prejemnik")
        prejemnik = Uporabnik.gql(
            "WHERE ime ='" + ime_uporabnika + "'").get()  # dobimo ime uporabnika (prejemnika) iz baze s GET()

        prejemnik = prejemnik.key.id()  # ID prejemnika
        naslov = self.request.get("naslov")
        vsebina = self.request.get("vsebina")
        #   datum = self.request.get("nastanek")   # datume generira avtomaticno

        vsebina = cgi.escape(vsebina)  # prepreci javascript injection

        sporocilo = Sporocilo(naslov_sporocila=naslov, vsebina_sporocila=vsebina, id_posiljatelja=posiljatelj_id,
                              id_prejemnika=prejemnik, ime_posiljatelja=posiljatelj, ime_prejemnika=ime_uporabnika)
        sporocilo.put()

        return self.write("You have successfully sent a message ...click back on your browser")

class PrejetaSporocilaHandler(BaseHandler):
    def get(self):

        cookie_value = self.request.cookies.get("uid")      # po cookie-u dobimo ID posiljatelja
        id_prijavljenega_uporabnika, _, _ = cookie_value.split(":")     # po cookie-u dobimo ID posiljatelja

        prejeta_sporocila = Sporocilo.gql("WHERE id_prejemnika =" + id_prijavljenega_uporabnika).fetch()    # dobimo prejeta sporocila uporabnika  iz baze s GET()

        params = {"seznam_sporocil": prejeta_sporocila}
        return self.render_template("prejeta_sporocila.html", params=params)


class PoslanaSporocilaHandler(BaseHandler): # implementirati se funkcijo za prikazovanje imena prejemnika namesto ID
    def get(self):

        cookie_value = self.request.cookies.get("uid")      # po cookie-u dobimo ID posiljatelja
        id_prijavljenega_uporabnika, _, _ = cookie_value.split(":")     # po cookie-u dobimo ID posiljatelja

        poslana_sporocila = Sporocilo.gql("WHERE id_posiljatelja =" + id_prijavljenega_uporabnika).fetch()      # dobimo poslana sporocila uporabnika iz baze s GET()

        params = {"seznam_sporocil": poslana_sporocila}
        return self.render_template("poslana_sporocila.html", params=params)


class WeatherHandler(BaseHandler):
    def get(self):

        url = "http://api.openweathermap.org/data/2.5/weather?q=Lljubljana&units=metric&appid=d23ef4ef1700cc9f89d46413ccdf2a96"     # API stran za vreme
        result = urlfetch.fetch(url)    # preko urlfetch dobimo result v json formatu
        podatki = json.loads(result.content)    # preko json.loads dobimo content
        params = {"podatki": podatki}

        self.render_template("vreme.html", params)


class LogoutHandler(BaseHandler):   # narediti log out funkcijo
    def get(self):
        self.redirect_to("main")


app = webapp2.WSGIApplication([
    webapp2.Route('/', MainHandler, name="main"),
    webapp2.Route('/registracija', RegistracijaHandler),
    webapp2.Route('/login', LoginHandler),
    webapp2.Route('/prejeto', PrejetoHandler),
    webapp2.Route('/novo-sporocilo', NovoSporociloHandler),
    webapp2.Route('/prejeta-sporocila', PrejetaSporocilaHandler),
    webapp2.Route('/poslana-sporocila', PoslanaSporocilaHandler),
    webapp2.Route('/vreme', WeatherHandler),
    webapp2.Route('/logout', LogoutHandler),
], debug=True)
