FROM nikolaik/python-nodejs:python3.10

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


RUN curl -fsSL https://deno.land/install.sh -o /tmp/deno-install.sh && \
    sh /tmp/deno-install.sh && \
    rm -f /tmp/deno-install.sh

ENV DENO_INSTALL=/root/.deno
ENV PATH=$DENO_INSTALL/bin:$PATH    

COPY . /app/
WORKDIR /app/
RUN python3 -m pip install --upgrade pip setuptools
RUN pip3 install --no-cache-dir --upgrade --requirement requirements.txt

CMD python3 -m VenomX
