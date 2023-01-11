FROM continuumio/miniconda3:4.12.0
RUN apt update && apt upgrade -y
RUN apt-get update
RUN apt-get install -y curl
RUN mkdir /sencast
COPY ./adapters /sencast/adapters
COPY ./dias_apis /sencast/dias_apis
COPY ./mosaic /sencast/mosaic
COPY ./postprocess /sencast/postprocess
COPY ./processors /sencast/processors
COPY ./utils /sencast/utils
COPY ./wkt /sencast/wkt
COPY ./constants.py /sencast/
COPY ./main.py /sencast/
COPY ./sencast-37.yml /sencast/
RUN conda env create -f /sencast/sencast-37.yml
ENV CONDA_HOME=/opt/conda
ENV CONDA_ENV_HOME=$CONDA_HOME/envs/sencast-37
RUN cd ~
RUN curl -O http://step.esa.int/downloads/9.0/installers/esa-snap_all_unix_9_0_0.sh
RUN chmod 755 esa-snap_all_unix_9_0_0.sh
RUN echo "o\n1\n\n\nn\nn\nn\n" | bash esa-snap_all_unix_9_0_0.sh
ENV SNAP_HOME=/opt/snap
RUN $SNAP_HOME/bin/snap --nosplash --nogui --modules --update-all
RUN $SNAP_HOME/bin/snap --nosplash --nogui --modules --install org.esa.snap.idepix.core org.esa.snap.idepix.probav org.esa.snap.idepix.modis org.esa.snap.idepix.spotvgt org.esa.snap.idepix.landsat8 org.esa.snap.idepix.viirs org.esa.snap.idepix.olci org.esa.snap.idepix.seawifs org.esa.snap.idepix.meris org.esa.snap.idepix.s2msi
RUN echo "#SNAP configuration 's3tbx'" >> ~/.snap/etc/s3tbx.properties
RUN echo "#Fri Mar 27 12:55:00 CET 2020" >> ~/.snap/etc/s3tbx.properties
RUN echo "s3tbx.reader.olci.pixelGeoCoding=true" >> ~/.snap/etc/s3tbx.properties
RUN echo "s3tbx.reader.meris.pixelGeoCoding=true" >> ~/.snap/etc/s3tbx.properties
RUN echo "s3tbx.reader.slstrl1b.pixelGeoCodings=true" >> ~/.snap/etc/s3tbx.properties