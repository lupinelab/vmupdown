FROM ubuntu/apache2

RUN apt-get -y update && apt-get install -y git python3 libapache2-mod-wsgi-py3 wakeonlan python3-pip iputils-ping --no-install-recommends

RUN pip3 install flask proxmoxer requests

RUN rm /var/www/html/index.html

COPY /vmupdown /var/www/html/vmupdown

RUN rm -rf /var/www/html/vmupdown/config/config.py

COPY /vmupdown.conf /etc/apache2/sites-available/

RUN chown -R www-data:www-data /var/www/html/vmupdown && chmod +x /var/www/html/vmupdown/vmupdown.*

RUN a2dissite 000-default && a2ensite vmupdown

RUN ln -sf /proc/self/fd/1 /var/log/apache2/access.log && ln -sf /proc/self/fd/1 /var/log/apache2/error.log

ENTRYPOINT ["/usr/sbin/apachectl", "-D", "FOREGROUND"]